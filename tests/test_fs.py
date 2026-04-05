import os
import time

from tradedangerous import fs

class TestFS:
    def test_copy(self, tmp_path):
        src = tmp_path / 'src.txt'
        dst = tmp_path / 'dst.txt'
        src.write_text('alpha', encoding='utf-8')
        
        copied = fs.copy(src, dst)
        
        assert copied == dst
        assert dst.read_text(encoding='utf-8') == 'alpha'
    
    def test_copyallfiles(self, tmp_path):
        srcdir = tmp_path / 'src'
        dstdir = tmp_path / 'dst'
        srcdir.mkdir()
        dstdir.mkdir()
        (srcdir / 'Added.csv').write_text('a', encoding='utf-8')
        (srcdir / 'skip.me').write_text('b', encoding='utf-8')
        (srcdir / 'README').write_text('c', encoding='utf-8')
        
        fs.copyallfiles(srcdir, dstdir)
        
        assert (dstdir / 'Added.csv').exists()
        assert (dstdir / 'skip.me').exists()
        assert (dstdir / 'README').exists()
    
    def test_copy_if_missing_preserves_existing_file(self, tmp_path):
        src = tmp_path / 'src.txt'
        dst = tmp_path / 'dst.txt'
        src.write_text('source', encoding='utf-8')
        dst.write_text('existing', encoding='utf-8')
        
        result = fs.copy_if_missing(src, dst)
        
        assert result == src.resolve()
        assert dst.read_text(encoding='utf-8') == 'existing'
    
    def test_copy_if_newer_respects_mtime(self, tmp_path):
        src = tmp_path / 'src.txt'
        dst = tmp_path / 'dst.txt'
        src.write_text('old-source', encoding='utf-8')
        dst.write_text('new-dest', encoding='utf-8')
        now = time.time()
        os.utime(src, (now - 20, now - 20))
        os.utime(dst, (now, now))
        
        result = fs.copy_if_newer(src, dst)
        assert result == src.resolve()
        assert dst.read_text(encoding='utf-8') == 'new-dest'
        
        src.write_text('new-source', encoding='utf-8')
        os.utime(src, (now + 20, now + 20))
        result = fs.copy_if_newer(src, dst)
        assert result == dst
        assert dst.read_text(encoding='utf-8') == 'new-source'
    
    def test_file_line_count_handles_missing_ok_and_no_final_newline(self, tmp_path):
        missing = tmp_path / 'missing.txt'
        text = tmp_path / 'lines.txt'
        text.write_text('one\ntwo\nthree', encoding='utf-8')
        
        assert fs.file_line_count(missing, missing_ok=True) == 0
        assert fs.file_line_count(text) == 2
