import os
import re
import sys
env={k:v for k,v in os.environ.items() if not re.fullmatch(r'(SUB|SRV|XRAY_JSON)[0-9]+(?:_[A-Za-z0-9]+)?',k)}
os.execve('/entrypoint.sh',['/entrypoint.sh']+sys.argv[1:],env)
