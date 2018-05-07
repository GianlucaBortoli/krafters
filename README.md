# Krafters

A black-box testing platform for message-based distributed algorithms. This 
tool provides a handy way to deploy a distributed environment, execute a 
distributed algorithm, orchestrate a series of tests and visualize the results.
The environment can be either pseudo-distributed, on localhost, or 
fully-distributed, on [Google Compute Engine](
https://cloud.google.com/compute/). Distributed algorithms must rely on message
passing and can be of any kind, such as [consensus algorithms](
https://en.wikipedia.org/wiki/Consensus_(computer_science)) (e.g. [Raft](
https://en.wikipedia.org/wiki/Raft_(computer_science)) and [Paxos](
https://en.wikipedia.org/wiki/Paxos_(computer_science))). Tests are performed 
by modifying the underlying network to introduce packet 
delay/loss/corruption/inversion via [netem](
https://wiki.linuxfoundation.org/networking/netem), a low-level Linux kernel 
tool. Their results can be visualized via plots automatically generated with 
[seaborn](https://seaborn.pydata.org/).

Please refer to the [project report](
https://github.com/GianlucaBortoli/krafters/blob/master/report/report.pdf) to 
get further insights on the software capabilities and to read how it has been 
used to compare different algorithms implementations and technologies, such as 
[RethinkDB](https://www.rethinkdb.com/), [Multi-Paxos](
https://github.com/cocagne/multi-paxos-example), [Google Datastore](
https://cloud.google.com/datastore/) and [PySyncObj](
https://github.com/bakwc/PySyncObj).


---
## Information

**Status**: `Completed`

**Type**: `Academic project`

**Course**: `Distributed algorithms`

**Development year(s)**: `2016`

**Authors**: [GianlucaBortoli](https://github.com/GianlucaBortoli) 
(VMs configuration, plots), [mfederici](https://github.com/mfederici) 
(test language, network manager), [ShadowTemplate](https://github.com/ShadowTemplate)
(GCE provisioning, test daemon)

---
## Getting Started

The project folder contains all the Python scripts required to run the 
platform. Each relevant script provides a helper describing its CLI parameters.

The starting point of the platform is the provisioner, that is responsible of 
deploying a cluster of machines and distribute the required daemon across them.
The provisioner can deploy up to 8 nodes (the default CPU quota on Google 
Compute Engine), either in a pseudo-distributed mode or in a fully-distributed mode. 
The available algorithms and technologies are 
[RethinkDB](https://www.rethinkdb.com/), 
[Multi-Paxos](https://github.com/cocagne/multi-paxos-example), 
[Google Datastore](https://cloud.google.com/datastore/) and 
[PySyncObj](https://github.com/bakwc/PySyncObj).
However, new ones can be easily added.

To deploy a local cluster of 6 machines running 
[PySyncObj](https://github.com/bakwc/PySyncObj), for instance, it is sufficient
to execute:

```
$ python3 provisioner.py -n 6 -m local -a pso
```

Similarly, to deploy a Google Compute Engine cluster of 8 machines running 
[RethinkDB](https://www.rethinkdb.com/), it is sufficient to execute:

```
$ python3 provisioner.py -n 8 -m gce -a rethinkdb
```

The provisioner will produce a JSON configuration file that can be later used 
to tear down the cluster. The majority of other Python/shell scripts are 
automatically distributed and executed on the cluster nodes.

### Prerequisites

Clone the repository and install the required Python dependencies:

```
$ git clone https://github.com/GianlucaBortoli/krafters.git
$ cd krafters
$ pip install --user -r requirements.txt
```

### Deployment

Make sure to set up the Google Cloud Platform project before running the 
provisioner. The script requires both Google Compute Engine and Google Cloud
Storage.

---
## Building tools

* [Python 3.4](https://www.python.org/downloads/release/python-340/) - 
Programming language
* [Python 2.7](https://www.python.org/downloads/release/python-270/) - 
Programming language
* Shell scripts - Configure VMs, generate plots
* [seaborn](https://seaborn.pydata.org/) - Data visualization
* [netem](https://wiki.linuxfoundation.org/networking/netem) - Network 
manipulation
* [Google Compute Engine](https://cloud.google.com/compute/) - Virtual machines
* [Google Cloud Storage](https://cloud.google.com/storage/) - File storage
* [gsutil](https://cloud.google.com/storage/docs/gsutil) - Google Cloud Storage
interface
* [RethinkDB](https://www.rethinkdb.com/) - Raft implementation
* [Multi-Paxos](https://github.com/cocagne/multi-paxos-example) - Paxos 
implementation
* [Google Datastore](https://cloud.google.com/datastore/) - Distributed 
algorithm implementation
* [PySyncObj](https://github.com/bakwc/PySyncObj) - Raft implementation

---
## Contributing

This project is not actively maintained and issues or pull requests may be 
ignored.

---
## License

This project is licensed under the GNU GPLv3 license.
Please refer to the [LICENSE.md](LICENSE.md) file for details.

---
*This README.md complies with [this project template](
https://github.com/ShadowTemplate/project-template). Feel free to adopt it
and reuse it.*
