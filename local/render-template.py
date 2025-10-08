#!/usr/bin/env python3
import os
import sys
from jinja2 import Template

template_file = sys.argv[1]
output_file = sys.argv[2]

with open(template_file, "r") as f:
    template = Template(f.read())

context = {
    "WEB_PORT": os.environ.get("WEB_PORT", "80"),
    "RTMP_PORT": os.environ.get("RTMP_PORT", "1935")
}

rendered = template.render(context)

with open(output_file, "w") as f:
    f.write(rendered)
