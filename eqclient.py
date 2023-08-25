#!/usr/bin/env python
# coding: utf-8

# In[1]:


import collections

import requests
from obspy.clients.fdsn import Client

# In[2]:


r = requests.get(
    "http://service.iris.edu/irisws/fedcatalog/1/query",
    params={
        "cha": "BHZ",
        "starttime": "1995-11-14T06:32:55.750000Z",
        "endtime": "1995-11-14T06:32:55.750000Z",
        "level": "channel",
        "format": "request",
        "includeoverlaps": "false",
        "nodata": 404,
    },
)


# In[3]:


records = collections.defaultdict(list)

current_datacenter = None
for line in r.text.splitlines():
    line = line.strip()

    if not line:  # skip empty lines
        continue

    # detect the start of a new datacenter
    if line.startswith("DATACENTER"):
        name, url = line.split("=")[1].split(",")
        name = "IRIS" if name == "IRISDMC" else name
        current_datacenter = name
        continue

    # skip lines before the first datacenter
    if current_datacenter is None:
        continue

    # skip more urls
    if "http://" in line or "https://" in line:
        continue
    records[current_datacenter].append(line)


# In[4]:


for datacenter in records.keys():
    if datacenter != "IRIS":
        continue
    print(datacenter)
    client = Client(datacenter, debug=True)
    inv = client.get_stations_bulk("\n".join(records[datacenter]))


# In[49]:


client = Client("IRIS")


# In[51]:


client.get_stations()


# In[52]:


from obspy.clients.fdsn import Client

# In[53]:


client = Client("IRIS")


# In[54]:


from obspy import UTCDateTime

t = UTCDateTime("2010-02-27T06:45:00.000")
st = client.get_waveforms("IU", "ANMO", "00", "LHZ", t, t + 60 * 60)
st.plot()


# In[ ]:
