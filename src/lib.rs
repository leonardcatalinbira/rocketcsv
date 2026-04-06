use pyo3::exceptions::{PyException, PyIndexError, PyTypeError};
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString};
use std::cell::RefCell;
use std::collections::HashMap;
use std::io::{self, Cursor, Read};
use std::rc::Rc;

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

pyo3::create_exception!(rocketcsv, CsvError, PyException, "rocketcsv.Error");

// ---------------------------------------------------------------------------
// PyIterableReader — bridges a Python iterable to Rust's `impl Read`
// ---------------------------------------------------------------------------

struct PyIterableReader {
    source: Py<PyAny>,
    is_file_like: bool,
    buf: Vec<u8>,
    pos: usize,
    exhausted: bool,
    total_bytes_buffered: usize,
}

impl PyIterableReader {
    fn new(py: Python<'_>, source: Py<PyAny>) -> PyResult<Self> {
        let is_file_like = source.bind(py).hasattr("read")?;
        // If not file-like, get an iterator via iter() so lists/tuples work
        let source = if is_file_like {
            source
        } else {
            let iter_obj = source.call_method0(py, "__iter__")?;
            iter_obj
        };
        Ok(Self {
            source,
            is_file_like,
            buf: Vec::new(),
            pos: 0,
            exhausted: false,
            total_bytes_buffered: 0,
        })
    }

    fn bulk_read(&mut self, py: Python<'_>) -> PyResult<()> {
        let content: String = self.source.call_method0(py, "read")?.extract(py)?;
        self.buf = content.into_bytes();
        self.total_bytes_buffered += self.buf.len();
        self.pos = 0;
        self.exhausted = true;
        Ok(())
    }

    fn fetch_next(&mut self, py: Python<'_>) -> PyResult<bool> {
        if self.exhausted {
            return Ok(false);
        }
        match self.source.call_method0(py, "__next__") {
            Ok(obj) => {
                let line: String = obj.extract(py)?;
                let bytes = line.as_bytes();
                self.total_bytes_buffered += bytes.len();
                self.buf.extend_from_slice(bytes);
                Ok(true)
            }
            Err(e) if e.is_instance_of::<pyo3::exceptions::PyStopIteration>(py) => {
                self.exhausted = true;
                Ok(false)
            }
            Err(e) => Err(e),
        }
    }
}

impl Read for PyIterableReader {
    fn read(&mut self, out: &mut [u8]) -> io::Result<usize> {
        if self.pos >= self.buf.len() {
            self.buf.clear();
            self.pos = 0;
            Python::with_gil(|py| {
                if self.is_file_like && !self.exhausted {
                    self.bulk_read(py)
                        .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
                } else {
                    self.fetch_next(py)
                        .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
                }
                Ok::<(), io::Error>(())
            })?;
        }
        let available = &self.buf[self.pos..];
        if available.is_empty() {
            return Ok(0);
        }
        let n = out.len().min(available.len());
        out[..n].copy_from_slice(&available[..n]);
        self.pos += n;
        Ok(n)
    }
}

// ---------------------------------------------------------------------------
// Adaptive per-column string cache
// ---------------------------------------------------------------------------

/// Per-column string value cache. Capped at max_entries per column.
/// When a column exceeds the cap, that column stops caching (adaptive).
/// 100% data accuracy — Python strings are immutable, reusing the same
/// object for identical values is safe.
struct ColumnCache {
    map: HashMap<Box<[u8]>, *mut ffi::PyObject>,
    active: bool,
}

struct StringInternPool {
    columns: Vec<ColumnCache>,
    max_per_col: usize,
    /// Cached empty string pointer.
    empty_str: *mut ffi::PyObject,
}

impl StringInternPool {
    fn new(py: Python<'_>, max_per_col: usize) -> Self {
        // Pre-create the empty string — most common value in CSV data
        let empty = unsafe {
            ffi::PyUnicode_FromStringAndSize(b"\0".as_ptr() as *const _, 0)
        };
        Self {
            columns: Vec::new(),
            max_per_col,
            empty_str: empty,
        }
    }

    /// Ensure we have at least `n` column caches.
    fn ensure_columns(&mut self, n: usize) {
        while self.columns.len() < n {
            self.columns.push(ColumnCache {
                map: HashMap::with_capacity(64),
                active: true,
            });
        }
    }

    /// Get or create a PyUnicode for field bytes. Goes bytes → PyUnicode
    /// directly via ffi, skipping Rust String allocation.
    /// Returns a NEW reference (caller owns it).
    #[inline]
    unsafe fn get_or_create(&mut self, col: usize, field: &[u8]) -> *mut ffi::PyObject {
        if field.is_empty() {
            ffi::Py_INCREF(self.empty_str);
            return self.empty_str;
        }

        let cache = &mut self.columns[col];

        if cache.active {
            if let Some(&ptr) = cache.map.get(field) {
                ffi::Py_INCREF(ptr);
                return ptr;
            }
        }

        // Create new PyUnicode directly from UTF-8 bytes — no Rust String intermediate
        let ptr = ffi::PyUnicode_FromStringAndSize(
            field.as_ptr() as *const _,
            field.len() as ffi::Py_ssize_t,
        );

        if cache.active {
            if cache.map.len() < self.max_per_col {
                ffi::Py_INCREF(ptr); // one ref for the cache, one for the caller
                cache.map.insert(field.into(), ptr);
            } else {
                // High cardinality column — stop caching, don't waste memory
                cache.active = false;
            }
        }

        ptr
    }
}

impl Drop for StringInternPool {
    fn drop(&mut self) {
        Python::with_gil(|_py| unsafe {
            // Release cached empty string
            ffi::Py_DECREF(self.empty_str);
            // Release all cached column strings
            for col in &self.columns {
                for &ptr in col.map.values() {
                    ffi::Py_DECREF(ptr);
                }
            }
        });
    }
}

// ---------------------------------------------------------------------------
// Fast list + field creation via raw ffi
// ---------------------------------------------------------------------------

/// Create a PyList and populate with SET_ITEM (skips bounds checks + refcounting).
/// `ptrs` contains new references — SET_ITEM steals them.
#[inline]
unsafe fn fast_list_from_ptrs(py: Python<'_>, ptrs: &[*mut ffi::PyObject]) -> PyObject {
    let n = ptrs.len() as ffi::Py_ssize_t;
    let list = ffi::PyList_New(n);
    for (i, &ptr) in ptrs.iter().enumerate() {
        ffi::PyList_SET_ITEM(list, i as ffi::Py_ssize_t, ptr);
    }
    PyObject::from_owned_ptr(py, list)
}

// ---------------------------------------------------------------------------
// Format parameters
// ---------------------------------------------------------------------------

fn configure_reader_builder(
    builder: &mut csv::ReaderBuilder,
    delimiter: Option<u8>,
    quotechar: Option<u8>,
    doublequote: Option<bool>,
    escapechar: Option<u8>,
    quoting: Option<u32>,
) {
    if let Some(d) = delimiter { builder.delimiter(d); }
    if let Some(q) = quotechar { builder.quote(q); }
    if let Some(dq) = doublequote { builder.double_quote(dq); }
    if let Some(esc) = escapechar { builder.escape(Some(esc)); }
    if let Some(3) = quoting { builder.quoting(false); }
    builder.has_headers(false);
}

fn configure_writer_builder(
    builder: &mut csv::WriterBuilder,
    delimiter: Option<u8>,
    quotechar: Option<u8>,
    doublequote: Option<bool>,
    escapechar: Option<u8>,
    quoting: Option<u32>,
    lineterminator: Option<String>,
) {
    if let Some(d) = delimiter { builder.delimiter(d); }
    if let Some(q) = quotechar { builder.quote(q); }
    if let Some(dq) = doublequote { builder.double_quote(dq); }
    if let Some(esc) = escapechar { builder.escape(esc); }
    if let Some(quoting_val) = quoting {
        let style = match quoting_val {
            0 => csv::QuoteStyle::Necessary,
            1 => csv::QuoteStyle::Always,
            2 => csv::QuoteStyle::NonNumeric,
            3 => csv::QuoteStyle::Never,
            _ => csv::QuoteStyle::Necessary,
        };
        builder.quote_style(style);
    }
    if let Some(term) = lineterminator {
        let terminator = match term.as_str() {
            "\r\n" => csv::Terminator::CRLF,
            s if s.len() == 1 => csv::Terminator::Any(s.as_bytes()[0]),
            _ => csv::Terminator::CRLF,
        };
        builder.terminator(terminator);
    }
}

// ---------------------------------------------------------------------------
// RocketReader — streaming reader with adaptive string interning
// ---------------------------------------------------------------------------

#[pyclass(unsendable)]
struct RocketReader {
    inner: csv::Reader<PyIterableReader>,
    record: csv::StringRecord,
    line_num: usize,
    quote_nonnumeric: bool,
    skipinitialspace: bool,
    yielded_any: bool,
    pool: StringInternPool,
    /// Reusable buffer for raw pointers (avoids per-row allocation)
    field_ptrs: Vec<*mut ffi::PyObject>,
}

#[pymethods]
impl RocketReader {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> { slf }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        match self.inner.read_record(&mut self.record) {
            Ok(true) => {
                self.line_num += 1;
                self.yielded_any = true;

                let n = self.record.len();
                self.pool.ensure_columns(n);
                self.field_ptrs.clear();

                if self.quote_nonnumeric {
                    for (i, field) in self.record.iter().enumerate() {
                        let f = if self.skipinitialspace {
                            field.strip_prefix(' ').unwrap_or(field)
                        } else { field };
                        match f.parse::<f64>() {
                            Ok(num) => {
                                let ptr = unsafe { ffi::PyFloat_FromDouble(num) };
                                self.field_ptrs.push(ptr);
                            }
                            Err(_) => {
                                let ptr = unsafe { self.pool.get_or_create(i, f.as_bytes()) };
                                self.field_ptrs.push(ptr);
                            }
                        }
                    }
                } else {
                    for (i, field) in self.record.iter().enumerate() {
                        let f = if self.skipinitialspace {
                            field.strip_prefix(' ').unwrap_or(field)
                        } else { field };
                        let ptr = unsafe { self.pool.get_or_create(i, f.as_bytes()) };
                        self.field_ptrs.push(ptr);
                    }
                }

                let list = unsafe { fast_list_from_ptrs(py, &self.field_ptrs) };
                Ok(Some(list))
            }
            Ok(false) => {
                if !self.yielded_any {
                    let had_input = self.inner.get_ref().total_bytes_buffered > 0;
                    if had_input {
                        self.yielded_any = true;
                        self.line_num += 1;
                        return Ok(Some(
                            PyList::new_bound(py, Vec::<PyObject>::new().as_slice())
                                .into_any().unbind(),
                        ));
                    }
                }
                Ok(None)
            }
            Err(e) => Err(CsvError::new_err(e.to_string())),
        }
    }

    #[getter]
    fn line_num(&self) -> usize { self.line_num }
}

// ---------------------------------------------------------------------------
// BulkReader — file path fast path, parse entirely in Rust
// ---------------------------------------------------------------------------

#[pyclass(unsendable)]
struct BulkReader {
    inner: csv::Reader<Cursor<Vec<u8>>>,
    record: csv::StringRecord,
    total_bytes: usize,
    line_num: usize,
    quote_nonnumeric: bool,
    skipinitialspace: bool,
    yielded_any: bool,
    pool: StringInternPool,
    field_ptrs: Vec<*mut ffi::PyObject>,
}

#[pymethods]
impl BulkReader {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> { slf }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        match self.inner.read_record(&mut self.record) {
            Ok(true) => {
                self.line_num += 1;
                self.yielded_any = true;

                let n = self.record.len();
                self.pool.ensure_columns(n);
                self.field_ptrs.clear();

                if self.quote_nonnumeric {
                    for (i, field) in self.record.iter().enumerate() {
                        let f = if self.skipinitialspace {
                            field.strip_prefix(' ').unwrap_or(field)
                        } else { field };
                        match f.parse::<f64>() {
                            Ok(num) => {
                                let ptr = unsafe { ffi::PyFloat_FromDouble(num) };
                                self.field_ptrs.push(ptr);
                            }
                            Err(_) => {
                                let ptr = unsafe { self.pool.get_or_create(i, f.as_bytes()) };
                                self.field_ptrs.push(ptr);
                            }
                        }
                    }
                } else {
                    for (i, field) in self.record.iter().enumerate() {
                        let f = if self.skipinitialspace {
                            field.strip_prefix(' ').unwrap_or(field)
                        } else { field };
                        let ptr = unsafe { self.pool.get_or_create(i, f.as_bytes()) };
                        self.field_ptrs.push(ptr);
                    }
                }

                let list = unsafe { fast_list_from_ptrs(py, &self.field_ptrs) };
                Ok(Some(list))
            }
            Ok(false) => {
                if !self.yielded_any && self.total_bytes > 0 {
                    self.yielded_any = true;
                    self.line_num += 1;
                    return Ok(Some(
                        PyList::new_bound(py, Vec::<PyObject>::new().as_slice())
                            .into_any().unbind(),
                    ));
                }
                Ok(None)
            }
            Err(e) => Err(CsvError::new_err(e.to_string())),
        }
    }

    #[getter]
    fn line_num(&self) -> usize { self.line_num }
}

// ---------------------------------------------------------------------------
// RocketWriter
// ---------------------------------------------------------------------------

#[pyclass]
struct RocketWriter {
    file: Py<PyAny>,
    delimiter: u8,
    quotechar: u8,
    doublequote: bool,
    escapechar: Option<u8>,
    quoting: u32,
    lineterminator: String,
    buf: Vec<u8>,
}

impl RocketWriter {
    fn collect_fields(row: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
        let iter = row.iter()?;
        let mut fields: Vec<String> = Vec::new();
        for item in iter {
            let item = item?;
            if item.is_none() { fields.push(String::new()); }
            else { fields.push(item.str()?.to_string()); }
        }
        Ok(fields)
    }

    fn make_builder(&self) -> csv::WriterBuilder {
        let mut b = csv::WriterBuilder::new();
        configure_writer_builder(
            &mut b, Some(self.delimiter), Some(self.quotechar),
            Some(self.doublequote), self.escapechar,
            Some(self.quoting), Some(self.lineterminator.clone()),
        );
        b
    }

    fn format_fields_into_buf(&mut self, fields: &[String], builder: &csv::WriterBuilder) -> PyResult<()> {
        self.buf.clear();
        if fields.is_empty() {
            self.buf.extend_from_slice(self.lineterminator.as_bytes());
            return Ok(());
        }
        let buf = std::mem::take(&mut self.buf);
        let mut wtr = builder.from_writer(buf);
        wtr.write_record(fields).map_err(|e| CsvError::new_err(e.to_string()))?;
        wtr.flush().map_err(|e| CsvError::new_err(e.to_string()))?;
        self.buf = wtr.into_inner().map_err(|e| CsvError::new_err(e.to_string()))?;
        Ok(())
    }
}

#[pymethods]
impl RocketWriter {
    fn writerow(&mut self, py: Python<'_>, row: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let fields = Self::collect_fields(row)?;
        let builder = self.make_builder();
        self.format_fields_into_buf(&fields, &builder)?;
        let text = std::str::from_utf8(&self.buf).map_err(|e| CsvError::new_err(e.to_string()))?;
        self.file.call_method1(py, "write", (text,))
    }

    fn writerows(&mut self, py: Python<'_>, rows: &Bound<'_, PyAny>) -> PyResult<()> {
        let mut output: Vec<u8> = Vec::with_capacity(8192);
        let wtr_builder = self.make_builder();
        let mut wtr = wtr_builder.from_writer(&mut output);
        let mut fields_buf: Vec<String> = Vec::with_capacity(32);

        for row in rows.iter()? {
            let row = row?;
            fields_buf.clear();
            for item in row.iter()? {
                let item = item?;
                if item.is_none() { fields_buf.push(String::new()); }
                else { fields_buf.push(item.str()?.to_string()); }
            }
            if fields_buf.is_empty() {
                wtr.flush().map_err(|e| CsvError::new_err(e.to_string()))?;
                drop(wtr);
                output.extend_from_slice(self.lineterminator.as_bytes());
                wtr = wtr_builder.from_writer(&mut output);
            } else {
                wtr.write_record(&fields_buf).map_err(|e| CsvError::new_err(e.to_string()))?;
            }
        }
        wtr.flush().map_err(|e| CsvError::new_err(e.to_string()))?;
        drop(wtr);
        let text = std::str::from_utf8(&output).map_err(|e| CsvError::new_err(e.to_string()))?;
        self.file.call_method1(py, "write", (text,))?;
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Module-level functions
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (csvfile, delimiter=None, quotechar=None, doublequote=None, escapechar=None, quoting=None, skipinitialspace=None, strict=None))]
fn reader(
    py: Python<'_>, csvfile: Py<PyAny>,
    delimiter: Option<&str>, quotechar: Option<&str>,
    doublequote: Option<bool>, escapechar: Option<&str>,
    quoting: Option<u32>, skipinitialspace: Option<bool>, strict: Option<bool>,
) -> PyResult<RocketReader> {
    let delim_byte = delimiter.map(|s| s.as_bytes()[0]);
    let quote_byte = quotechar.map(|s| s.as_bytes()[0]);
    let esc_byte = escapechar.map(|s| s.as_bytes()[0]);
    let py_reader = PyIterableReader::new(py, csvfile)?;
    let mut builder = csv::ReaderBuilder::new();
    configure_reader_builder(&mut builder, delim_byte, quote_byte, doublequote, esc_byte, quoting);
    builder.flexible(!strict.unwrap_or(false));
    let csv_reader = builder.from_reader(py_reader);

    Ok(RocketReader {
        inner: csv_reader,
        record: csv::StringRecord::new(),
        line_num: 0,
        quote_nonnumeric: quoting == Some(2),
        skipinitialspace: skipinitialspace.unwrap_or(false),
        yielded_any: false,
        pool: StringInternPool::new(py, 8192),
        field_ptrs: Vec::with_capacity(32),
    })
}

#[pyfunction]
#[pyo3(signature = (path, delimiter=None, quotechar=None, doublequote=None, escapechar=None, quoting=None, skipinitialspace=None, strict=None))]
fn reader_from_path(
    py: Python<'_>, path: &str,
    delimiter: Option<&str>, quotechar: Option<&str>,
    doublequote: Option<bool>, escapechar: Option<&str>,
    quoting: Option<u32>, skipinitialspace: Option<bool>, strict: Option<bool>,
) -> PyResult<BulkReader> {
    let delim_byte = delimiter.map(|s| s.as_bytes()[0]);
    let quote_byte = quotechar.map(|s| s.as_bytes()[0]);
    let esc_byte = escapechar.map(|s| s.as_bytes()[0]);

    let content = std::fs::read(path)
        .map_err(|e| CsvError::new_err(format!("Cannot read {}: {}", path, e)))?;
    let total_bytes = content.len();

    let mut builder = csv::ReaderBuilder::new();
    configure_reader_builder(&mut builder, delim_byte, quote_byte, doublequote, esc_byte, quoting);
    builder.flexible(!strict.unwrap_or(false));

    let csv_reader = builder.from_reader(Cursor::new(content));

    Ok(BulkReader {
        inner: csv_reader,
        record: csv::StringRecord::new(),
        total_bytes,
        line_num: 0,
        quote_nonnumeric: quoting == Some(2),
        skipinitialspace: skipinitialspace.unwrap_or(false),
        yielded_any: false,
        pool: StringInternPool::new(py, 8192),
        field_ptrs: Vec::with_capacity(32),
    })
}

#[pyfunction]
#[pyo3(signature = (csvfile, delimiter=None, quotechar=None, doublequote=None, escapechar=None, quoting=None, lineterminator=None))]
fn writer(
    _py: Python<'_>, csvfile: Py<PyAny>,
    delimiter: Option<&str>, quotechar: Option<&str>,
    doublequote: Option<bool>, escapechar: Option<&str>,
    quoting: Option<u32>, lineterminator: Option<&str>,
) -> PyResult<RocketWriter> {
    Ok(RocketWriter {
        file: csvfile,
        delimiter: delimiter.map(|s| s.as_bytes()[0]).unwrap_or(b','),
        quotechar: quotechar.map(|s| s.as_bytes()[0]).unwrap_or(b'"'),
        doublequote: doublequote.unwrap_or(true),
        escapechar: escapechar.map(|s| s.as_bytes()[0]),
        quoting: quoting.unwrap_or(0),
        lineterminator: lineterminator.unwrap_or("\r\n").to_string(),
        buf: Vec::with_capacity(1024),
    })
}

// ---------------------------------------------------------------------------
// RocketRow — lazy Rust-backed row, creates PyString only on access
// ---------------------------------------------------------------------------

/// Shared cross-row intern cache. Rows hold Rc to this.
struct SharedInternPool {
    columns: Vec<HashMap<Box<[u8]>, Py<PyString>>>,
    max_per_col: usize,
}

impl SharedInternPool {
    fn new(max_per_col: usize) -> Self {
        Self { columns: Vec::new(), max_per_col }
    }

    fn ensure_columns(&mut self, n: usize) {
        while self.columns.len() < n {
            self.columns.push(HashMap::with_capacity(64));
        }
    }

    fn get_or_create(&mut self, py: Python<'_>, col: usize, field: &[u8]) -> Py<PyString> {
        if let Some(cached) = self.columns[col].get(field) {
            return cached.clone_ref(py);
        }

        let s = unsafe {
            let ptr = ffi::PyUnicode_FromStringAndSize(
                field.as_ptr() as *const _,
                field.len() as ffi::Py_ssize_t,
            );
            Py::from_owned_ptr(py, ptr)
        };

        if self.columns[col].len() < self.max_per_col {
            self.columns[col].insert(field.into(), s.clone_ref(py));
        }

        s
    }
}

#[pyclass(unsendable)]
struct RocketRow {
    /// Compact storage: all field bytes concatenated.
    data: Vec<u8>,
    /// offsets[i] = byte start of field i. offsets[len] = end sentinel.
    offsets: Vec<usize>,
    /// Column indices (for interning).
    col_count: usize,
    /// Shared intern pool across all rows from the same reader.
    pool: Rc<RefCell<SharedInternPool>>,
    /// Lazily created PyString cache per field (None = not yet accessed).
    py_cache: Vec<Option<Py<PyString>>>,
}

impl RocketRow {
    fn field_bytes(&self, idx: usize) -> &[u8] {
        &self.data[self.offsets[idx]..self.offsets[idx + 1]]
    }

    fn get_pystring(&mut self, py: Python<'_>, idx: usize) -> Py<PyString> {
        if let Some(ref cached) = self.py_cache[idx] {
            return cached.clone_ref(py);
        }

        let bytes = self.field_bytes(idx);
        let s = self.pool.borrow_mut().get_or_create(py, idx, bytes);
        self.py_cache[idx] = Some(s.clone_ref(py));
        s
    }
}

#[pymethods]
impl RocketRow {
    fn __len__(&self) -> usize {
        self.col_count
    }

    fn __getitem__(&mut self, py: Python<'_>, idx: isize) -> PyResult<PyObject> {
        let n = self.col_count as isize;
        let actual = if idx < 0 { n + idx } else { idx };
        if actual < 0 || actual >= n {
            return Err(PyIndexError::new_err("list index out of range"));
        }
        Ok(self.get_pystring(py, actual as usize).into_any())
    }

    fn __iter__(slf: Bound<'_, Self>) -> PyResult<PyObject> {
        // Return an iterator that yields fields in order
        let py = slf.py();
        let mut inner = slf.borrow_mut();
        let n = inner.col_count;
        let mut items: Vec<PyObject> = Vec::with_capacity(n);
        for i in 0..n {
            items.push(inner.get_pystring(py, i).into_any());
        }
        // Return a plain list iterator
        let list = PyList::new_bound(py, &items);
        Ok(list.call_method0("__iter__")?.unbind())
    }

    fn __contains__(&mut self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<bool> {
        let target: String = value.extract()?;
        let target_bytes = target.as_bytes();
        for i in 0..self.col_count {
            if self.field_bytes(i) == target_bytes {
                return Ok(true);
            }
        }
        Ok(false)
    }

    fn __eq__(&mut self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        // Support comparison with list[str]
        if let Ok(other_list) = other.downcast::<PyList>() {
            if other_list.len() != self.col_count {
                return Ok(false);
            }
            for i in 0..self.col_count {
                let other_str: String = other_list.get_item(i)?.extract()?;
                if other_str.as_bytes() != self.field_bytes(i) {
                    return Ok(false);
                }
            }
            return Ok(true);
        }
        Ok(false)
    }

    fn __repr__(&mut self, py: Python<'_>) -> PyResult<String> {
        let mut parts = Vec::with_capacity(self.col_count);
        for i in 0..self.col_count {
            let s = std::str::from_utf8(self.field_bytes(i))
                .map_err(|e| PyTypeError::new_err(e.to_string()))?;
            parts.push(format!("'{}'", s.replace('\'', "\\'")));
        }
        Ok(format!("[{}]", parts.join(", ")))
    }
}

// ---------------------------------------------------------------------------
// FastReader — performance mode, yields lazy RocketRow
// ---------------------------------------------------------------------------

#[pyclass(unsendable)]
struct FastReader {
    inner: csv::Reader<Cursor<Vec<u8>>>,
    byte_record: csv::ByteRecord,
    line_num: usize,
    skipinitialspace: bool,
    yielded_any: bool,
    total_bytes: usize,
    pool: Rc<RefCell<SharedInternPool>>,
}

#[pymethods]
impl FastReader {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> { slf }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        match self.inner.read_byte_record(&mut self.byte_record) {
            Ok(true) => {
                self.line_num += 1;
                self.yielded_any = true;

                let n = self.byte_record.len();
                self.pool.borrow_mut().ensure_columns(n);

                // Build compact row storage
                let mut data = Vec::with_capacity(128);
                let mut offsets = Vec::with_capacity(n + 1);

                for field in self.byte_record.iter() {
                    offsets.push(data.len());
                    if self.skipinitialspace && field.first() == Some(&b' ') {
                        data.extend_from_slice(&field[1..]);
                    } else {
                        data.extend_from_slice(field);
                    }
                }
                offsets.push(data.len());

                let py_cache: Vec<Option<Py<PyString>>> = (0..n).map(|_| None).collect();
                let row = RocketRow {
                    data,
                    offsets,
                    col_count: n,
                    pool: Rc::clone(&self.pool),
                    py_cache,
                };

                Ok(Some(Py::new(py, row)?.into_any()))
            }
            Ok(false) => {
                if !self.yielded_any && self.total_bytes > 0 {
                    self.yielded_any = true;
                    self.line_num += 1;
                    let row = RocketRow {
                        data: Vec::new(),
                        offsets: vec![0],
                        col_count: 0,
                        pool: Rc::clone(&self.pool),
                        py_cache: Vec::new(),
                    };
                    return Ok(Some(Py::new(py, row)?.into_any()));
                }
                Ok(None)
            }
            Err(e) => Err(CsvError::new_err(e.to_string())),
        }
    }

    #[getter]
    fn line_num(&self) -> usize { self.line_num }
}

/// fast_reader from file path — performance mode.
#[pyfunction]
#[pyo3(signature = (path, delimiter=None, quotechar=None, doublequote=None, escapechar=None, quoting=None, skipinitialspace=None, strict=None))]
fn fast_reader_from_path(
    _py: Python<'_>, path: &str,
    delimiter: Option<&str>, quotechar: Option<&str>,
    doublequote: Option<bool>, escapechar: Option<&str>,
    quoting: Option<u32>, skipinitialspace: Option<bool>, strict: Option<bool>,
) -> PyResult<FastReader> {
    let delim_byte = delimiter.map(|s| s.as_bytes()[0]);
    let quote_byte = quotechar.map(|s| s.as_bytes()[0]);
    let esc_byte = escapechar.map(|s| s.as_bytes()[0]);

    let content = std::fs::read(path)
        .map_err(|e| CsvError::new_err(format!("Cannot read {}: {}", path, e)))?;
    let total_bytes = content.len();

    let mut builder = csv::ReaderBuilder::new();
    configure_reader_builder(&mut builder, delim_byte, quote_byte, doublequote, esc_byte, quoting);
    builder.flexible(!strict.unwrap_or(false));

    Ok(FastReader {
        inner: builder.from_reader(Cursor::new(content)),
        byte_record: csv::ByteRecord::new(),
        line_num: 0,
        skipinitialspace: skipinitialspace.unwrap_or(false),
        yielded_any: false,
        total_bytes,
        pool: Rc::new(RefCell::new(SharedInternPool::new(8192))),
    })
}

/// fast_reader from Python file/StringIO — performance mode.
#[pyfunction]
#[pyo3(signature = (csvfile, delimiter=None, quotechar=None, doublequote=None, escapechar=None, quoting=None, skipinitialspace=None, strict=None))]
fn fast_reader(
    py: Python<'_>, csvfile: Py<PyAny>,
    delimiter: Option<&str>, quotechar: Option<&str>,
    doublequote: Option<bool>, escapechar: Option<&str>,
    quoting: Option<u32>, skipinitialspace: Option<bool>, strict: Option<bool>,
) -> PyResult<FastReader> {
    let delim_byte = delimiter.map(|s| s.as_bytes()[0]);
    let quote_byte = quotechar.map(|s| s.as_bytes()[0]);
    let esc_byte = escapechar.map(|s| s.as_bytes()[0]);

    // Bulk-read content from Python
    let content: Vec<u8> = if csvfile.bind(py).hasattr("read")? {
        let text: String = csvfile.call_method0(py, "read")?.extract(py)?;
        text.into_bytes()
    } else {
        // Iterable: collect all lines
        let mut buf = Vec::new();
        loop {
            match csvfile.call_method0(py, "__next__") {
                Ok(obj) => {
                    let line: String = obj.extract(py)?;
                    buf.extend_from_slice(line.as_bytes());
                }
                Err(e) if e.is_instance_of::<pyo3::exceptions::PyStopIteration>(py) => break,
                Err(e) => return Err(e),
            }
        }
        buf
    };
    let total_bytes = content.len();

    let mut builder = csv::ReaderBuilder::new();
    configure_reader_builder(&mut builder, delim_byte, quote_byte, doublequote, esc_byte, quoting);
    builder.flexible(!strict.unwrap_or(false));

    Ok(FastReader {
        inner: builder.from_reader(Cursor::new(content)),
        byte_record: csv::ByteRecord::new(),
        line_num: 0,
        skipinitialspace: skipinitialspace.unwrap_or(false),
        yielded_any: false,
        total_bytes,
        pool: Rc::new(RefCell::new(SharedInternPool::new(8192))),
    })
}

// ---------------------------------------------------------------------------
// Module definition
// ---------------------------------------------------------------------------

#[pymodule]
fn _rocketcsv(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(reader, m)?)?;
    m.add_function(wrap_pyfunction!(reader_from_path, m)?)?;
    m.add_function(wrap_pyfunction!(fast_reader, m)?)?;
    m.add_function(wrap_pyfunction!(fast_reader_from_path, m)?)?;
    m.add_function(wrap_pyfunction!(writer, m)?)?;
    m.add_class::<RocketReader>()?;
    m.add_class::<BulkReader>()?;
    m.add_class::<FastReader>()?;
    m.add_class::<RocketRow>()?;
    m.add_class::<RocketWriter>()?;
    m.add("Error", m.py().get_type_bound::<CsvError>())?;
    m.add("QUOTE_MINIMAL", 0u32)?;
    m.add("QUOTE_ALL", 1u32)?;
    m.add("QUOTE_NONNUMERIC", 2u32)?;
    m.add("QUOTE_NONE", 3u32)?;
    m.add("QUOTE_STRINGS", 4u32)?;
    m.add("QUOTE_NOTNULL", 5u32)?;
    Ok(())
}
