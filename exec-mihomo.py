import os
import re
import sys
from network import prepare_environment
env={k:v for k,v in os.environ.items() if not re.fullmatch(r'(SUB|SRV|XRAY_JSON)[0-9]+(?:_[A-Za-z0-9]+)?',k)}
prepare_environment(env)
os.execve('/entrypoint.sh',['/entrypoint.sh']+sys.argv[1:],env)
