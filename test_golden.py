import pytest
import tempfile
import os
import logging
import contextlib
import io
import warnings
import translator, machine

warnings.filterwarnings("ignore", category=pytest.PytestRemovedIn10Warning)

@pytest.mark.golden_test("golden/*.yml")
def test_golden(golden, caplog):
    caplog.set_level(logging.DEBUG)
    # caplog.handler.setFormatter(logging.Formatter("%(message)s"))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        source = os.path.join(tmpdir, "source.kst")
        target = os.path.join(tmpdir, "target.bin")
        input_data = os.path.join(tmpdir, "input.txt")

        with open(source, "w", encoding="utf-8") as f:
            f.write(golden["in_source"])
        
        with open(input_data, "w", encoding="utf-8") as f:
            f.write(golden["in_input"])

        translator.main(source, target)

        log_io = io.StringIO()
        log_handler = logging.StreamHandler(log_io)
        log_handler.setFormatter(logging.Formatter("%(message)s"))
        
        root_logger = logging.getLogger()
        old_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(log_handler)
        
        try:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                machine.main(target, input_data)
            out_stdout = stdout.getvalue()
        finally:
            root_logger.removeHandler(log_handler)
            root_logger.setLevel(old_level)
            
        with open(target + ".log", "r", encoding="utf-8") as f:
            code_log = f.read()

        assert code_log.strip() == golden.out["out_code"].strip()
        assert out_stdout.strip() == golden.out["out_stdout"].strip()
        assert log_io.getvalue().strip() == golden.out["out_log"].strip()