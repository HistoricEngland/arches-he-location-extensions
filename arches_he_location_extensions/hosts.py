import re
from django_hosts import patterns, host

host_patterns = patterns(
    "",
    host(
        re.sub(r"_", r"-", r"arches_he_location_extensions"),
        "arches_he_location_extensions.urls",
        name="arches_he_location_extensions",
    ),
)
