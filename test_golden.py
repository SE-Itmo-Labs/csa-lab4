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
    caplog.handler.setFormatter(logging.Formatter("%(message)s"))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        source = os.path.join(tmpdir, "source.kst")
        target = os.path.join(tmpdir, "target.bin")
        input_data = os.path.join(tmpdir, "input.txt")

        with open(source, "w", encoding="utf-8") as f:
            f.write(golden["in_source"])
        
        with open(input_data, "w", encoding="utf-8") as f:
            f.write(golden["in_input"])

        translator.main(source, target)
        
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            machine.main(target, input_data)
            
        with open(target + ".log", "r", encoding="utf-8") as f:
            code_log = f.read()

        assert code_log.strip() == golden.out["out_code"].strip()
        assert stdout.getvalue().strip() == golden.out["out_stdout"].strip()