import os
from pathlib import Path
assert os.environ['DOCTOR_FIXTURE'] == 'reviewed'
assert Path.cwd() == Path('/workspace/app')
print('DOCTOR_STATE_SUCCESS', flush=True)
