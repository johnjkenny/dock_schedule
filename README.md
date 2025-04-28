# Dock-Schedule

Dock-Schedule is a job application for scheduling and managing jobs using a docker swarm cluster

The swarm stack consists of the following services:
- broker: rabbitmq message broker
- container_scraper: cadvisor container scraper to pull container metrics (global service, runs on all nodes)
- grafana: grafana for visualizing metrics
- mongodb: mongodb for storing and updating job data
- mongodb_scraper: mongodb scraper to pull database metrics
- node_scraper: node exporter to pull swarm host metrics (global service, runs on all nodes)
- prometheus: prometheus server for collecting and storing metrics from scrape jobs (runs on manager node)
- proxy: nginx reverse proxy for routing requests to the appropriate service and for SSL/TLS termination
- proxy_scraper: nginx scraper to pull nginx metrics
- registry: docker registry for storing the docker images used by the swarm services (runs on manager node)
- scheduler: scheduler service for scheduling jobs in the swarm cluster (runs on manager node)
- worker: worker service for executing jobs in the swarm cluster

The proxy service exposes ports `80`, `443`, and `8080`. `80` reroutes to `443` and `443` routes to grafana service UI.
Port `8080` routes to prometheus service UI where you can see the state of the swarm metric scrape jobs as well as run
queries against the data. You can also use `/api/v1/query` URI to query the prometheus API for metrics.

The worker can handle python, bash, php, javascript (npm/node), and ansible jobs. By default there are three worker replicas
within the swarm cluster. Each worker can queue a total of 3 jobs at a time which means a total of 9 jobs can be
delivered to the swarm workers at a time by default. The message broker service will hold onto the remaining queued jobs
until a worker completes and acknowledges a job. You can view the broker queue in the grafana dashboard which will show you
how many messages (jobs) are waiting to be delivered to the workers. You can increase/decrease the number of worker
replicas based on the backlog of jobs in the queue. Depending on the resources you have available on your swarm manager
node you may also have to increase/decrease the number of swarm nodes within the cluster to handle the load of the
worker demand.


# Command Overview:

```bash
dschedule -h
usage: dschedule [-h] [-I ...] [-S ...] [-w ...] [-s ...] [-c ...] [-j ...]

Dock Schedule Parent Commands

options:
  -h, --help            show this help message and exit

  -I ..., --init ...    Initialize dock-schedule environment

  -S ..., --swarm ...   Dock Schedule swarm commands

  -w ..., --workers ...
                        Dock Schedule worker commands

  -s ..., --services ...
                        Dock Schedule service commands

  -c ..., --containers ...
                        Dock Schedule container commands

  -j ..., --jobs ...    Dock Schedule job commands
```

# Initialization
The idea is to have a VM or physical server as the initial swarm manager node. Clone the repository to the server you
wish to use as the primary swam cluster node. A 2 CPU, 2GB RAM server with 20GB storage is sufficient for the initial
deployment with low work load. Scale up the cluster as needed.

The initialization process creates the directory `/opt/dock-schedule` on the swarm manager node. The service, job, and
configuration files are copied from the git repository clone to this directory tree. The init process creates the
service users, the directory tree, a certificate store to generate the TLS host and service certificates, generates
ansible ssh keys, installs NFS, exports `/opt/dock-schedule` directory as a NFS share using the swarm manager subnet,
installs docker, creates a docker swarm, creates the docker swarm networks and secrets for the services, installs
firewalld and opens up the required NFS and Docker ports, builds the docker images, and then starts the swarm stack
services.

The generated ansible private ssh key is `/opt/dock-schedule/ansible/.env/.ansible_rsa`. Ansible is used to configure
new nodes added to the swarm cluster. You will need to the ansible public key
`/opt/dock-schedule/ansible/.env/.ansible_rsa.pub` to be added to the `~/.ssh/authorized_keys` on the ansible user of
the new swam nodes you add to the cluster. You can either keep the generated ansible ssh keys and deploy the public key
to new nodes or you can replace the ansible ssh keys with your own. The private and public keys are also used to run
ansible worker jobs so any remote ansible jobs will also require to have the same ansible public key added to the
ansible user's `~/.ssh/authorized_keys` file.

Since we are using NFS to share the `/opt/dock-schedule` directory tree across the swarm cluster you do not have to
install the git repository on each node. When adding new nodes to the swarm cluster the export will be mounted on each
swarm node. Several services have persistent storage volumes assigned to then which are also shared via NFS in the
swarm. The host and services need to have the same user ID and group ID for the permissions and ownership to work
correctly. Each user is given the following UID/GID on the swarm hosts and within the container services:

- grafana: 3000 UID, 3000 GID
- rabbitmq: 3001 UID, 3001 GID
- mongodb: 3002 UID, 3002 GID


1. Install the required dependencies:
It is recommended to create a python virtual environment on the export directory so it can be used on all swarm nodes
in the cluster without the need to install the dependencies on each node. As part of the init process, if
`/opt/dock-schedule/venv` directory exists then an entry will be added to `/root/.bashrc` to activate the virtual
environment on every new shell session. This will give you access to the `dschedule` command regardless of the current
directory you are in or swarm node type, but keep in mind that not all commands will work on all nodes at this time.
Some commands will only work on the swarm manager node.

```bash
# Create the directory:
mkdir -p /opt/dock-schedule

# create a virtual environment:
python3 -m venv /opt/dock-schedule/venv

# activate the virtual environment:
source /opt/dock-schedule/venv/bin/activate

# Install python dependencies:
pip install -r requirements.txt

# install the console scripts:
pip install -e .
```


2. Initialize the dock-schedule environment:
```bash
# Command Options:
dschedule -I -h
usage: dschedule [-h] [-r] [-F] [-N]

Dock Schedule: Initialization

options:
  -h, --help            show this help message and exit

  -r, --run             Run initialization

  -F, --force           Force operations

  -N, --nonInteractive  Run in non-interactive mode


# run initialization:
dschedule -I -r -N
[2025-04-28 18:53:59,692][INFO][init,27]: Creating service users
[2025-04-28 18:54:00,210][INFO][init,51]: Creating swarm directory tree
[2025-04-28 18:54:00,233][INFO][init,87]: Creating dock-schedule directory tree
[2025-04-28 18:54:28,133][INFO][init,97]: Initializing certificate store
[2025-04-28 18:54:35,158][INFO][init,161]: Generating SSL certificates for swarm manager
[2025-04-28 18:54:35,639][INFO][init,179]: Creating ansible keys
[2025-04-28 18:54:35,881][INFO][init,203]: Creating docker swarm

PLAY [Create Docker Swarm] *****************************************************

TASK [Gathering Facts] *********************************************************
ok: [localhost]

TASK [Venv exists] *************************************************************
ok: [localhost]

TASK [Create RC entry for venv] ************************************************
changed: [localhost]

TASK [Install NFS (RedHat)] ****************************************************
ok: [localhost]

TASK [Enable and start NFS server] *********************************************
ok: [localhost]

TASK [Parse Export Subnet] *****************************************************
ok: [localhost]

TASK [Create Swarm-Share NFS Export] *******************************************
changed: [localhost]

TASK [Update NFS Exports] ******************************************************
changed: [localhost]

TASK [Install dependencies (YUM/DNF)] ******************************************
changed: [localhost]

TASK [Set up Docker repo on RedHat-family systems] *****************************
changed: [localhost]

TASK [Install Docker CE] *******************************************************
changed: [localhost]

TASK [Enable and start Docker service] *****************************************
changed: [localhost]

TASK [Ensure docker directory exists] ******************************************
ok: [localhost]

TASK [Copy node TLS CA to Docker directory] ************************************
changed: [localhost]

TASK [Copy node TLS cert to Docker directory] **********************************
changed: [localhost]

TASK [Copy node TLS key to Docker directory] ***********************************
changed: [localhost]

TASK [Create node TLS PEM file] ************************************************
changed: [localhost]

TASK [Set TLS cert permissions] ************************************************
changed: [localhost]

TASK [Set Docker daemon config] ************************************************
changed: [localhost]

TASK [Restart Docker service] **************************************************
changed: [localhost]

TASK [Initialize Docker Swarm] *************************************************
changed: [localhost]

TASK [Create Metrics Network] **************************************************
changed: [localhost]

TASK [Create Broker Network] ***************************************************
changed: [localhost]

TASK [Create Job DB Network] ***************************************************
changed: [localhost]

TASK [Create Broker Secrets] ***************************************************
changed: [localhost]

TASK [Create Mong Secrets] *****************************************************
changed: [localhost]

TASK [Install Firewalld] *******************************************************
ok: [localhost]

TASK [Start Firewalld] *********************************************************
ok: [localhost]

TASK [Open Swarm TCP management port (2377)] ***********************************
changed: [localhost]

TASK [Open Swarm communication ports (7946 tcp/udp)] ***************************
changed: [localhost] => (item=7946/tcp)
changed: [localhost] => (item=7946/udp)

TASK [Open overlay network port (4789/udp)] ************************************
changed: [localhost]

TASK [Open NFS port (2049/tcp)] ************************************************
changed: [localhost]

TASK [Open HTTP Port (80/tcp)] *************************************************
changed: [localhost]

TASK [Open HTTPS Port (443/tcp)] ***********************************************
changed: [localhost]

TASK [Open Prometheus Port (8080/tcp)] *****************************************
changed: [localhost]

TASK [Build Registry Service] **************************************************
changed: [localhost]

TASK [Start Registry Service] **************************************************
changed: [localhost]

TASK [Build docker images] *****************************************************
changed: [localhost]

TASK [Push docker images] ******************************************************
changed: [localhost]

TASK [Start Swarm Services] ****************************************************
changed: [localhost]

PLAY RECAP *********************************************************************
localhost                  : ok=40   changed=32   unreachable=0    failed=0    skipped=4    rescued=0    ignored=0   
[2025-04-28 19:01:53,274][INFO][init,212]: Successfully initialized dock-schedule
```

# Swarm

You can use the `dschedule --swarm` command to add/remove nodes from the swarm cluster. You can also list the nodes in
the cluster and if you use the `--verbose` option you can get a snapshot of the container resource usage on each node
in the cluster. 

Command Options:
```bash
dschedule -S -h
usage: dschedule [-h] [-a] [-R] [-n NAME] [-i IP] [-l] [-v]

Dock Schedule: Swarm

options:
  -h, --help            show this help message and exit

  -a, --addNode         Add a node to the dock-schedule swarm

  -R, --removeNode      Remove a node from the dock-schedule swarm

  -n NAME, --name NAME  Name of the node to add or remove

  -i IP, --ip IP        IP address of the node to add or remove

  -l, --listNodes       List all nodes in the dock-schedule swarm

  -v, --verbose         Enable verbose output
```


1. Add a node to the swarm cluster:

You must specify the node name `--name, -n` and the IP address `--ip, -i` of the node you want to add to the swarm.
The process will use ansible to configure the node join and service deployment. The ansible public key must be in
`/home/ansible/.ssh/authorized_keys` on the node to be added (this has to be done manually or part of your node
deployment process). The ansible playbook will create the service users, install NFS, mount the NFS share,
install docker, install firewalld and open the required ports, create the service hosts file entries, joins the swarm,
pulls the docker images from the swarm registry, then rebalance the swarm services making the newly added node a host
to several swarm services.

```bash
dschedule -S -a -n dock-schedule-2 -i 192.168.122.52
[2025-04-28 20:09:56,305][INFO][swarm,190]: Adding dock-schedule-2 to swarm cluster

PLAY [Add Node to Swarm] *******************************************************

TASK [Gathering Facts] *********************************************************
ok: [dock-schedule-2]

TASK [Get Docker Swarm manager IP] *********************************************
ok: [dock-schedule-2 -> localhost]

TASK [Set fact for Swarm manager IP] *******************************************
ok: [dock-schedule-2 -> localhost]

TASK [Get join-token] **********************************************************
changed: [dock-schedule-2 -> localhost]

TASK [Set Swarm worker token fact] *********************************************
ok: [dock-schedule-2 -> localhost]

TASK [Create service groups] ***************************************************
changed: [dock-schedule-2] => (item=['grafana', 3000])
changed: [dock-schedule-2] => (item=['rabbitmq', 3001])
changed: [dock-schedule-2] => (item=['mongodb', 3002])

TASK [Create service users] ****************************************************
changed: [dock-schedule-2] => (item=['grafana', 3000])
changed: [dock-schedule-2] => (item=['rabbitmq', 3001])
changed: [dock-schedule-2] => (item=['mongodb', 3002])

TASK [Install Firewalld] *******************************************************
ok: [dock-schedule-2]

TASK [Start Firewalld] *********************************************************
ok: [dock-schedule-2]

TASK [Open Swarm TCP management port (2377)] ***********************************
changed: [dock-schedule-2]

TASK [Open Swarm communication ports (7946 tcp/udp)] ***************************
changed: [dock-schedule-2] => (item=7946/tcp)
changed: [dock-schedule-2] => (item=7946/udp)

TASK [Open overlay network port (4789/udp)] ************************************
changed: [dock-schedule-2]

TASK [Open NFS port (2049/tcp)] ************************************************
changed: [dock-schedule-2]

TASK [Open HTTP Port (80/tcp)] *************************************************
changed: [dock-schedule-2]

TASK [Open HTTPS Port (443/tcp)] ***********************************************
changed: [dock-schedule-2]

TASK [Open Prometheus Port (8080/tcp)] *****************************************
changed: [dock-schedule-2]

TASK [Install NFS (RedHat)] ****************************************************
ok: [dock-schedule-2]

TASK [Enable and start NFS client] *********************************************
ok: [dock-schedule-2]

TASK [Create swarm share directory] ********************************************
changed: [dock-schedule-2]

TASK [Mount swarm NFS share] ***************************************************
changed: [dock-schedule-2]

TASK [Venv exists] *************************************************************
ok: [dock-schedule-2]

TASK [Create RC entry for venv] ************************************************
changed: [dock-schedule-2]

TASK [Install dependencies (YUM/DNF)] ******************************************
changed: [dock-schedule-2]

TASK [Set up Docker repo on RedHat-family systems] *****************************
changed: [dock-schedule-2]

TASK [Install Docker CE] *******************************************************
changed: [dock-schedule-2]

TASK [Enable and start Docker service] *****************************************
changed: [dock-schedule-2]

TASK [Add service host entries] ************************************************
changed: [dock-schedule-2] => (item=127.0.0.1  proxy)
changed: [dock-schedule-2] => (item=127.0.0.1  mongodb)
changed: [dock-schedule-2] => (item=127.0.0.1  registry)

TASK [Join the Swarm] **********************************************************
changed: [dock-schedule-2]

TASK [Wait for registry service to propagate] **********************************
ok: [dock-schedule-2]

TASK [Pull docker service images] **********************************************
changed: [dock-schedule-2]

TASK [Broker Service Force Update] *********************************************
changed: [dock-schedule-2 -> localhost]

TASK [Grafana Service Force Update] ********************************************
changed: [dock-schedule-2 -> localhost]

TASK [MongoDB Service Force Update] ********************************************
changed: [dock-schedule-2 -> localhost]

TASK [MongoDB-Scraper Service Force Update] ************************************
changed: [dock-schedule-2 -> localhost]

TASK [Proxy Service Force Update] **********************************************
changed: [dock-schedule-2 -> localhost]

TASK [Proxy-Scraper Service Force Update] **************************************
changed: [dock-schedule-2 -> localhost]

TASK [Worker Service Force Update] *********************************************
changed: [dock-schedule-2 -> localhost]

PLAY RECAP *********************************************************************
dock-schedule-2            : ok=37   changed=27   unreachable=0    failed=0    skipped=4    rescued=0    ignored=0
```

2. Remove a node from the swarm cluster:
You must specify the node name `--name, -n` and the IP address `--ip, -i` of the node you want to remove from the swarm.
The ansible public key should already be in `/home/ansible/.ssh/authorized_keys` from the add node process. The remove
process will set the availability of the node to drain, wait for all services to relocate, leaves the swarm, removes
the service host entries, unmounts the NFS share, closes the swarm firewalld ports, stops the NFS client service, then
removes the node on the swarm manager node.

```bash
dschedule -S -R -n dock-schedule-2 -i 192.168.122.52
[2025-04-28 21:18:28,134][INFO][swarm,194]: Removing dock-schedule-2 from swarm cluster

PLAY [Remove Node from Swarm] **************************************************

TASK [Gathering Facts] *********************************************************
ok: [dock-schedule-2]

TASK [Get Docker Swarm manager IP] *********************************************
ok: [dock-schedule-2 -> localhost]

TASK [Set fact for Swarm manager IP] *******************************************
ok: [dock-schedule-2 -> localhost]

TASK [Drain node of services] **************************************************
changed: [dock-schedule-2 -> localhost]
FAILED - RETRYING: [dock-schedule-2]: Wait for node drain to complete (60 retries left).
FAILED - RETRYING: [dock-schedule-2]: Wait for node drain to complete (59 retries left).
FAILED - RETRYING: [dock-schedule-2]: Wait for node drain to complete (58 retries left).
FAILED - RETRYING: [dock-schedule-2]: Wait for node drain to complete (57 retries left).

TASK [Wait for node drain to complete] *****************************************
changed: [dock-schedule-2]

TASK [Leave swarm] *************************************************************
changed: [dock-schedule-2]

TASK [Remove service host entries] *********************************************
changed: [dock-schedule-2] => (item=127.0.0.1  proxy)
changed: [dock-schedule-2] => (item=127.0.0.1  mongodb)
changed: [dock-schedule-2] => (item=127.0.0.1  registry)

TASK [Create RC entry for venv] ************************************************
changed: [dock-schedule-2]

TASK [Unmount swarm NFS share] *************************************************
changed: [dock-schedule-2]

TASK [Close Swarm TCP management port (2377)] **********************************
changed: [dock-schedule-2]

TASK [Close Swarm communication ports (7946 tcp/udp)] **************************
changed: [dock-schedule-2] => (item=7946/tcp)
changed: [dock-schedule-2] => (item=7946/udp)

TASK [Close overlay network port (4789/udp)] ***********************************
changed: [dock-schedule-2]

TASK [Close NFS port (2049/tcp)] ***********************************************
changed: [dock-schedule-2]

TASK [Close HTTP Port (80/tcp)] ************************************************
changed: [dock-schedule-2]

TASK [Close HTTPS Port (443/tcp)] **********************************************
changed: [dock-schedule-2]

TASK [Close Prometheus Port (8080/tcp)] ****************************************
changed: [dock-schedule-2]

TASK [Disable and Stop NFS client] *********************************************
changed: [dock-schedule-2]

TASK [Remove node from swarm] **************************************************
changed: [dock-schedule-2 -> localhost]

PLAY RECAP *********************************************************************
dock-schedule-2            : ok=18   changed=15   unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

3. List nodes in the swarm cluster:
```bash
dschedule -S -l
dock-schedule-1 (192.168.122.110) [Leader]
dock-schedule-2 (192.168.122.52) 
dock-schedule-3 (192.168.122.195)


# use --verbose to get a snapshot of the container resource usage on each node
dschedule -S -l -v
dock-schedule-1 (192.168.122.110) [Leader]
    CPU Load Avg (1m):    27.0%
    CPU Load Avg (5m):    15.5%
    CPU Load Avg (15m):   15.0%
    Memory Used:          1.25 GiB (72.3%)
    Disk Used:            10.04 GiB (53.2%)
    Containers:
	dock-schedule_container_scraper.ak2u8rfw0rvkxats1xdo7ei24.mivhizytuiw5carb03d43n9yy
	    CPU (1m):    1.3%
	    Memory Used: 73.73 MiB (5.7%)
	dock-schedule_node_scraper.ak2u8rfw0rvkxats1xdo7ei24.njq2xs9c5aupjzhmme7ep0w5f
	    CPU (1m):    0.1%
	    Memory Used: 23.58 MiB (1.8%)
	dock-schedule_prometheus.1.l85aok9ch5no5xx19n5ew5pz6
	    CPU (1m):    0.3%
	    Memory Used: 236.14 MiB (18.4%)
	dock-schedule_scheduler.1.z97qs1ppqmzcbn446meofj5o5
	    CPU (1m):    0.1%
	    Memory Used: 37.52 MiB (2.9%)
	dock-schedule_registry.1.vd71m8xo5upeniwcjxea4v5lb
	    CPU (1m):    0.1%
	    Memory Used: 48.01 MiB (3.7%)
	dock-schedule_worker.3.urdulnpt126vjuzf77tn0yl60
	    CPU (1m):    0.1%
	    Memory Used: 30.64 MiB (2.4%)
	dock-schedule_worker.6.w4dtupal2i5cqnb8bcrn21uil
	    CPU (1m):    0.1%
	    Memory Used: 30.46 MiB (2.4%)
	dock-schedule_worker.22.mm4yq3pv1pwjaxwuh9e2e47vk
	    CPU (1m):    0.1%
	    Memory Used: 28.79 MiB (2.2%)
	dock-schedule_worker.5.pbzr4llaylxua5bmmlyox4z49
	    CPU (1m):    0.1%
	    Memory Used: 28.82 MiB (2.2%)
	dock-schedule_worker.20.ql0zbt8k04bkt1c73v73wmfmk
	    CPU (1m):    0.1%
	    Memory Used: 30.26 MiB (2.4%)
	dock-schedule_worker.4.rw3vqbimkcvyyzb6a7ub8ogf3
	    CPU (1m):    0.1%
	    Memory Used: 29.70 MiB (2.3%)
	dock-schedule_worker.21.sp4b43ei9ovx7cp5dxx2wgyar
	    CPU (1m):    0.1%
	    Memory Used: 30.45 MiB (2.4%)
	dock-schedule_worker.15.uzng625apyq1wz9l63dohhh0t
	    CPU (1m):    0.1%
	    Memory Used: 29.02 MiB (2.3%)
	dock-schedule_worker.18.w3dyejtbwd6q9d16bst9trioc
	    CPU (1m):    0.1%
	    Memory Used: 30.00 MiB (2.3%)
dock-schedule-2 (192.168.122.52)
    CPU Load Avg (1m):    5.5%
    CPU Load Avg (5m):    8.5%
    CPU Load Avg (15m):   4.0%
    Memory Used:          1.00 GiB (57.5%)
    Disk Used:            6.42 GiB (34.0%)
    Containers:
	dock-schedule_container_scraper.tzyvedvj816i7a424jtheeq26.pugem72m90c5lnd6xenyvid0q
	    CPU (1m):    1.1%
	    Memory Used: 68.12 MiB (6.7%)
	dock-schedule_node_scraper.tzyvedvj816i7a424jtheeq26.r48fr9s64wwywus531yq24wgo
	    CPU (1m):    0.1%
	    Memory Used: 11.98 MiB (1.2%)
	dock-schedule_mongodb_scraper.1.psdpoatklqwylhmvjb8715sx1
	    CPU (1m):    0.4%
	    Memory Used: 22.50 MiB (2.2%)
	dock-schedule_proxy.1.q6kbw4tes2pyls2tp2xt1miw8
	    CPU (1m):    0.1%
	    Memory Used: 3.85 MiB (0.4%)
	dock-schedule_proxy_scraper.1.wc9nvelydvjekh19dwctlm7br
	    CPU (1m):    0.1%
	    Memory Used: 27.16 MiB (2.7%)
	dock-schedule_worker.1.mwr6h969b8obzop6ka80d0gp4
	    CPU (1m):    0.1%
	    Memory Used: 29.38 MiB (2.9%)
	dock-schedule_worker.11.50b4ot8ykpk5p0537n9tdyt17
	    CPU (1m):    0.1%
	    Memory Used: 30.29 MiB (3.0%)
	dock-schedule_worker.16.6di2yc4ycwid3pjxyborz343k
	    CPU (1m):    0.1%
	    Memory Used: 29.60 MiB (2.9%)
	dock-schedule_worker.8.7ike6tiyj1eikrc3j573wwxjs
	    CPU (1m):    0.1%
	    Memory Used: 31.41 MiB (3.1%)
	dock-schedule_worker.14.qsx7ed8kq3c37lir3mv9kdl27
	    CPU (1m):    0.1%
	    Memory Used: 29.12 MiB (2.9%)
	dock-schedule_worker.13.rr1tqlkhgdv5g60o5ku65y3ts
	    CPU (1m):    0.1%
	    Memory Used: 28.62 MiB (2.8%)
	dock-schedule_worker.25.ugc29b3jc130nwqbnbeh3lb0y
	    CPU (1m):    0.1%
	    Memory Used: 30.32 MiB (3.0%)
	dock-schedule_worker.19.x6qob1v6gy5hkjr0wxybs9vsq
	    CPU (1m):    0.1%
	    Memory Used: 29.52 MiB (2.9%)
dock-schedule-3 (192.168.122.195) 
    CPU Load Avg (1m):    11.0%
    CPU Load Avg (5m):    26.0%
    CPU Load Avg (15m):   26.0%
    Memory Used:          1.14 GiB (65.6%)
    Disk Used:            6.42 GiB (34.0%)
    Containers:
	dock-schedule_broker.1.kbxcq4ckouxlzvs5jg4mpb0wl
	    CPU (1m):    0.3%
	    Memory Used: 111.36 MiB (9.6%)
	dock-schedule_container_scraper.jaj2f3zwj3zcyzz0cpdexy1uh.jmapdpjz1ohn0fqqs298lcgd9
	    CPU (1m):    1.2%
	    Memory Used: 73.62 MiB (6.3%)
	dock-schedule_grafana.1.zgz5g8txdsyjtoa996q5wogeh
	    CPU (1m):    0.1%
	    Memory Used: 220.87 MiB (19.0%)
	dock-schedule_node_scraper.jaj2f3zwj3zcyzz0cpdexy1uh.sqjza0go5goyiow1w92f7we9t
	    CPU (1m):    0.1%
	    Memory Used: 24.32 MiB (2.1%)
	dock-schedule_mongodb.1.jx01jg0ngyszuic2lojkpux0v
	    CPU (1m):    0.4%
	    Memory Used: 251.97 MiB (21.6%)
	dock-schedule_worker.2.m4qdjznv2m74jkk2tklg02f26
	    CPU (1m):    0.1%
	    Memory Used: 61.50 MiB (5.3%)
	dock-schedule_worker.17.8fkxy16jb4ka13zccahspxn6s
	    CPU (1m):    0.1%
	    Memory Used: 28.63 MiB (2.5%)
	dock-schedule_worker.9.dg02m30priccipruyfclldtmx
	    CPU (1m):    0.1%
	    Memory Used: 28.64 MiB (2.5%)
	dock-schedule_worker.24.f8beiegbwqxdb4y2rkrswvupw
	    CPU (1m):    0.1%
	    Memory Used: 29.22 MiB (2.5%)
	dock-schedule_worker.7.l99vlwp0ryl3fbyn9gtmff54c
	    CPU (1m):    0.1%
	    Memory Used: 29.47 MiB (2.5%)
	dock-schedule_worker.23.r5uyc12zzdj965f11qc21eqy8
	    CPU (1m):    0.1%
	    Memory Used: 29.54 MiB (2.5%)
	dock-schedule_worker.12.vhiauii005qp747uh1stpiqwi
	    CPU (1m):    0.1%
	    Memory Used: 27.92 MiB (2.4%)
	dock-schedule_worker.10.wwiq39tb3o940mmxq08j1gz33
	    CPU (1m):    0.1%
	    Memory Used: 29.15 MiB (2.5%)
```

# Services
You can use the `dschedule --service` command to handle the swarm services. Options entail starting, stopping,
reloading, rebalancing, and listing swarm services. This option can only be run on the swarm manager node.

Command Options:
```bash
dschedule -s -h
usage: dschedule [-h] [-B] [-s [START]] [-S [STOP]] [-R RELOAD] [-l] [-v]

Dock Schedule: Services

options:
  -h, --help            show this help message and exit

  -B, --balance         Balance the dock-schedule services among swarm nodes

  -s [START], --start [START]
                        Start the dock-schedule service(s). Specify service name for specific
                        service, else "all" is used. Use comma separated list for multiple services
                        (example: service1,service2)

  -S [STOP], --stop [STOP]
                        Stop the dock-schedule service(s). Specify service name for specific
                        service, else "all" is used. Use comma separated list for multiple services
                        (example: service1,service2)

  -R RELOAD, --reload RELOAD
                        Reload a dock-schedule service (specify service name or ID). Use comma
                        separated list for multiple services (example: service1,service2). Use "all"
                        to reload all services.

  -l, --list            List dock-schedule services and their status

  -v, --verbose         Enable verbose output
```

1. List services in the swarm:

```bash
dschedule -s -l
+--------------+-------------------+-------------------------------------------------+-----------+
|      ID      |        Name       |                      Image                      |  Replicas |
+--------------+-------------------+-------------------------------------------------+-----------+
| x1ttfkaj3wt9 |       broker      |       registry:5000/dschedule_broker:1.0.0      |    1/1    |
| clqo6tjg1151 | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |    3/3    |
| w3ebeq2eqaya |      grafana      |      registry:5000/dschedule_grafana:1.0.0      |    1/1    |
| oya0ra84x5ei |      mongodb      |      registry:5000/dschedule_mongodb:1.0.0      |    1/1    |
| aj8ta6x9i66c |  mongodb_scraper  |  registry:5000/dschedule_mongodb_scraper:1.0.0  |    1/1    |
| zifge6w9j6t8 |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |    3/3    |
| eus5a1saw2t4 |     prometheus    |     registry:5000/dschedule_prometheus:1.0.0    |    1/1    |
| d1ucq64nl0p4 |       proxy       |       registry:5000/dschedule_proxy:1.0.0       |    1/1    |
| kq3h92df82qc |   proxy_scraper   |   registry:5000/dschedule_proxy_scraper:1.0.0   |    1/1    |
| tbtlv1wvdfsf |      registry     |      registry:5000/dschedule_registry:1.0.0     |    1/1    |
| 5v0jddxza549 |     scheduler     |     registry:5000/dschedule_scheduler:1.0.0     |    1/1    |
| ys2kt7xmd3gx |       worker      |       registry:5000/dschedule_worker:1.0.0      |   25/25   |
|      -       |         -         |                        -                        | Total: 40 |
+--------------+-------------------+-------------------------------------------------+-----------+

# Use the --verbose option to view a little more information in json format:
dschedule -s -l -v
{
  "ID": "x1ttfkaj3wt9",
  "Image": "registry:5000/dschedule_broker:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_broker",
  "Ports": "",
  "Replicas": "1/1"
}
{
  "ID": "clqo6tjg1151",
  "Image": "registry:5000/dschedule_container_scraper:1.0.0",
  "Mode": "global",
  "Name": "dock-schedule_container_scraper",
  "Ports": "",
  "Replicas": "3/3"
}
{
  "ID": "w3ebeq2eqaya",
  "Image": "registry:5000/dschedule_grafana:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_grafana",
  "Ports": "",
  "Replicas": "1/1"
}
{
  "ID": "oya0ra84x5ei",
  "Image": "registry:5000/dschedule_mongodb:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_mongodb",
  "Ports": "*:27017->27017/tcp",
  "Replicas": "1/1"
}
{
  "ID": "aj8ta6x9i66c",
  "Image": "registry:5000/dschedule_mongodb_scraper:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_mongodb_scraper",
  "Ports": "",
  "Replicas": "1/1"
}
{
  "ID": "zifge6w9j6t8",
  "Image": "registry:5000/dschedule_node_scraper:1.0.0",
  "Mode": "global",
  "Name": "dock-schedule_node_scraper",
  "Ports": "",
  "Replicas": "3/3"
}
{
  "ID": "eus5a1saw2t4",
  "Image": "registry:5000/dschedule_prometheus:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_prometheus",
  "Ports": "",
  "Replicas": "1/1"
}
{
  "ID": "d1ucq64nl0p4",
  "Image": "registry:5000/dschedule_proxy:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_proxy",
  "Ports": "*:80->80/tcp, *:443->443/tcp, *:8080->8080/tcp",
  "Replicas": "1/1"
}
{
  "ID": "kq3h92df82qc",
  "Image": "registry:5000/dschedule_proxy_scraper:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_proxy_scraper",
  "Ports": "",
  "Replicas": "1/1"
}
{
  "ID": "tbtlv1wvdfsf",
  "Image": "registry:5000/dschedule_registry:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_registry",
  "Ports": "*:5000->5000/tcp",
  "Replicas": "1/1"
}
{
  "ID": "5v0jddxza549",
  "Image": "registry:5000/dschedule_scheduler:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_scheduler",
  "Ports": "",
  "Replicas": "1/1"
}
{
  "ID": "ys2kt7xmd3gx",
  "Image": "registry:5000/dschedule_worker:1.0.0",
  "Mode": "replicated",
  "Name": "dock-schedule_worker",
  "Ports": "",
  "Replicas": "25/25"
}
```

2. Reload swarm service:
You can reload a service using the `--reload` option. This will force the service to redeploy and remove the
currently running container once the new container is in a healthy state. You can use the `--all` option to reload all
services which is similar to running `--balance` option, but it will also reload the services that are pinned to the
manager node as well as the global services which do not have an impact on the rebalancing efforts. You can use this
method to basically clear the entire swarm state, but note, it takes quite awhile to reload all of the services.

```bash
dschedule -s -R scheduler
[2025-04-28 22:09:03,120][INFO][swarm,222]: Reloading scheduler service

# All services:
dschedule -s -R all
[2025-04-28 22:10:53,040][INFO][swarm,222]: Reloading proxy_scraper service
[2025-04-28 22:11:12,073][INFO][swarm,222]: Reloading broker service
[2025-04-28 22:11:37,418][INFO][swarm,222]: Reloading grafana service
[2025-04-28 22:11:56,426][INFO][swarm,222]: Reloading container_scraper service
[2025-04-28 22:12:42,813][INFO][swarm,222]: Reloading mongodb_scraper service
[2025-04-28 22:13:01,826][INFO][swarm,222]: Reloading node_scraper service
[2025-04-28 22:13:48,417][INFO][swarm,222]: Reloading proxy service
[2025-04-28 22:14:15,624][INFO][swarm,222]: Reloading worker service
[2025-04-28 22:24:15,184][INFO][swarm,222]: Reloading mongodb service
[2025-04-28 22:24:44,328][INFO][swarm,222]: Reloading prometheus service
[2025-04-28 22:25:03,391][INFO][swarm,222]: Reloading scheduler service

# multiple service reload:
dschedule -s -R mongodb,proxy
[2025-04-28 22:26:23,113][INFO][swarm,222]: Reloading mongodb service
[2025-04-28 22:26:52,354][INFO][swarm,222]: Reloading proxy service

dschedule -s -R "grafana, mongodb_scraper"
[2025-04-28 22:27:46,757][INFO][swarm,222]: Reloading mongodb_scraper service
[2025-04-28 22:28:05,782][INFO][swarm,222]: Reloading grafana service

# reload the registry service (cannot start or stop registry service):
dschedule -s -R registry
[2025-04-28 23:04:41,739][INFO][swarm,222]: Reloading registry service
```

3. Stopping swarm service:
You can use the service `--stop` option to stop a swarm service. You can omit a service name to stop all services, but
the registry service. The registry service cannot be started or stopped via the `dschedule` command; it can only be
reloaded. You can also specify `all` which does the same or you can specify one or multiple services to stop. Use the
name of service to stop it and not the ID.


```bash
dschedule -s -S worker
[2025-04-28 22:29:14,576][INFO][swarm,319]: Stopping worker service

dschedule -s -l
+--------------+-------------------+-------------------------------------------------+-----------+
|      ID      |        Name       |                      Image                      |  Replicas |
+--------------+-------------------+-------------------------------------------------+-----------+
| x1ttfkaj3wt9 |       broker      |       registry:5000/dschedule_broker:1.0.0      |    1/1    |
| clqo6tjg1151 | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |    3/3    |
| w3ebeq2eqaya |      grafana      |      registry:5000/dschedule_grafana:1.0.0      |    1/1    |
| oya0ra84x5ei |      mongodb      |      registry:5000/dschedule_mongodb:1.0.0      |    1/1    |
| aj8ta6x9i66c |  mongodb_scraper  |  registry:5000/dschedule_mongodb_scraper:1.0.0  |    1/1    |
| zifge6w9j6t8 |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |    3/3    |
| eus5a1saw2t4 |     prometheus    |     registry:5000/dschedule_prometheus:1.0.0    |    1/1    |
| d1ucq64nl0p4 |       proxy       |       registry:5000/dschedule_proxy:1.0.0       |    1/1    |
| kq3h92df82qc |   proxy_scraper   |   registry:5000/dschedule_proxy_scraper:1.0.0   |    1/1    |
| tbtlv1wvdfsf |      registry     |      registry:5000/dschedule_registry:1.0.0     |    1/1    |
| 5v0jddxza549 |     scheduler     |     registry:5000/dschedule_scheduler:1.0.0     |    1/1    |
|      -       |         -         |                        -                        | Total: 15 |
+--------------+-------------------+-------------------------------------------------+-----------+

# multiple service stop:
dschedule -s -S mongodb,proxy
[2025-04-28 22:30:42,875][INFO][swarm,319]: Stopping mongodb service
[2025-04-28 22:30:42,910][INFO][swarm,319]: Stopping proxy service

dschedule -s -l
+--------------+-------------------+-------------------------------------------------+-----------+
|      ID      |        Name       |                      Image                      |  Replicas |
+--------------+-------------------+-------------------------------------------------+-----------+
| x1ttfkaj3wt9 |       broker      |       registry:5000/dschedule_broker:1.0.0      |    1/1    |
| clqo6tjg1151 | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |    3/3    |
| w3ebeq2eqaya |      grafana      |      registry:5000/dschedule_grafana:1.0.0      |    1/1    |
| aj8ta6x9i66c |  mongodb_scraper  |  registry:5000/dschedule_mongodb_scraper:1.0.0  |    1/1    |
| zifge6w9j6t8 |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |    3/3    |
| eus5a1saw2t4 |     prometheus    |     registry:5000/dschedule_prometheus:1.0.0    |    1/1    |
| kq3h92df82qc |   proxy_scraper   |   registry:5000/dschedule_proxy_scraper:1.0.0   |    1/1    |
| tbtlv1wvdfsf |      registry     |      registry:5000/dschedule_registry:1.0.0     |    1/1    |
| 5v0jddxza549 |     scheduler     |     registry:5000/dschedule_scheduler:1.0.0     |    1/1    |
|      -       |         -         |                        -                        | Total: 13 |
+--------------+-------------------+-------------------------------------------------+-----------+

# Stop all services:
dschedule -s -S
[2025-04-28 22:42:07,316][INFO][swarm,319]: Stopping proxy service
[2025-04-28 22:42:07,338][INFO][swarm,319]: Stopping broker service
[2025-04-28 22:42:07,355][INFO][swarm,319]: Stopping node_scraper service
[2025-04-28 22:42:07,373][INFO][swarm,319]: Stopping proxy_scraper service
[2025-04-28 22:42:07,392][INFO][swarm,319]: Stopping prometheus service
[2025-04-28 22:42:07,413][INFO][swarm,319]: Stopping mongodb service
[2025-04-28 22:42:07,443][INFO][swarm,319]: Stopping container_scraper service
[2025-04-28 22:42:07,459][INFO][swarm,319]: Stopping grafana service
[2025-04-28 22:42:07,486][INFO][swarm,319]: Stopping scheduler service
[2025-04-28 22:42:07,502][INFO][swarm,319]: Stopping worker service
[2025-04-28 22:42:07,520][INFO][swarm,319]: Stopping mongodb_scraper service

dschedule -s -l
+--------------+----------+----------------------------------------+----------+
|      ID      |   Name   |                 Image                  | Replicas |
+--------------+----------+----------------------------------------+----------+
| nysr2eody3wm | registry | registry:5000/dschedule_registry:1.0.0 |   1/1    |
|      -       |    -     |                   -                    | Total: 1 |
+--------------+----------+----------------------------------------+----------+

dschedule -s -S broker,grafana
[2025-04-28 22:54:00,324][INFO][swarm,319]: Stopping broker service
[2025-04-28 22:54:00,353][INFO][swarm,319]: Stopping grafana service

dschedule -s -l
+--------------+-------------------+-------------------------------------------------+-----------+
|      ID      |        Name       |                      Image                      |  Replicas |
+--------------+-------------------+-------------------------------------------------+-----------+
| 6y5cn34imra2 | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |    3/3    |
| ns8jkh90wwb3 |      mongodb      |      registry:5000/dschedule_mongodb:1.0.0      |    1/1    |
| j5q99dt9wjwg |  mongodb_scraper  |  registry:5000/dschedule_mongodb_scraper:1.0.0  |    1/1    |
| jd4z4knjrri6 |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |    3/3    |
| scxll31i8bjv |     prometheus    |     registry:5000/dschedule_prometheus:1.0.0    |    1/1    |
| oaxalul7rrah |       proxy       |       registry:5000/dschedule_proxy:1.0.0       |    1/1    |
| wfl4wf01w66n |   proxy_scraper   |   registry:5000/dschedule_proxy_scraper:1.0.0   |    1/1    |
| nysr2eody3wm |      registry     |      registry:5000/dschedule_registry:1.0.0     |    1/1    |
| pj2zx2vyq9fc |     scheduler     |     registry:5000/dschedule_scheduler:1.0.0     |    1/1    |
| 8daroy53ir7l |       worker      |       registry:5000/dschedule_worker:1.0.0      |    3/3    |
|      -       |         -         |                        -                        | Total: 16 |
+--------------+-------------------+-------------------------------------------------+-----------+

# error trying to stop registry service
dschedule -s -S registry
[2025-04-28 22:54:57,672][ERROR][swarm,345]: Cannot stop service "registry"
```

4. Start swarm services:
You can use the service `--start` option to start a swarm service. You can omit a service name to start all services, but
the registry service. The registry service cannot be started or stopped via the `dschedule` command; it can only be
reloaded. You can also specify `all` which does the same or you can specify one or multiple services to start.

```bash
# start all swarm services
dschedule -s -s
[2025-04-28 23:01:46,394][INFO][swarm,263]: Starting services: all

# wait for the services to init and transition into healthy state:
dschedule -s -l
+--------------+-------------------+-------------------------------------------------+-----------+
|      ID      |        Name       |                      Image                      |  Replicas |
+--------------+-------------------+-------------------------------------------------+-----------+
| 7xawnjrfpmou |       broker      |       registry:5000/dschedule_broker:1.0.0      |    1/1    |
| jfto3c8ly352 | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |    3/3    |
| c9brx67jw93a |      grafana      |      registry:5000/dschedule_grafana:1.0.0      |    1/1    |
| otmewxhcg45m |      mongodb      |      registry:5000/dschedule_mongodb:1.0.0      |    1/1    |
| kh9ksl225x2m |  mongodb_scraper  |  registry:5000/dschedule_mongodb_scraper:1.0.0  |    1/1    |
| b8ilmwlw3om1 |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |    3/3    |
| oo1p3q6637ud |     prometheus    |     registry:5000/dschedule_prometheus:1.0.0    |    1/1    |
| snwyydqmae01 |       proxy       |       registry:5000/dschedule_proxy:1.0.0       |    1/1    |
| fwjkmow52ouf |   proxy_scraper   |   registry:5000/dschedule_proxy_scraper:1.0.0   |    1/1    |
| nysr2eody3wm |      registry     |      registry:5000/dschedule_registry:1.0.0     |    1/1    |
| n7u6xnx2kr0k |     scheduler     |     registry:5000/dschedule_scheduler:1.0.0     |    1/1    |
| 4nubmqeicumb |       worker      |       registry:5000/dschedule_worker:1.0.0      |    3/3    |
|      -       |         -         |                        -                        | Total: 18 |
+--------------+-------------------+-------------------------------------------------+-----------+

# start multiple services:
dschedule -s -s broker,scheduler,worker
[2025-04-28 23:03:58,638][INFO][swarm,263]: Starting services: broker,scheduler,worker
dschedule -s -l
+--------------+-----------+-----------------------------------------+----------+
|      ID      |    Name   |                  Image                  | Replicas |
+--------------+-----------+-----------------------------------------+----------+
| w0xud9ffoxzr |   broker  |   registry:5000/dschedule_broker:1.0.0  |   1/1    |
| nysr2eody3wm |  registry |  registry:5000/dschedule_registry:1.0.0 |   1/1    |
| 8etd4y9b4n7g | scheduler | registry:5000/dschedule_scheduler:1.0.0 |   1/1    |
| dt4x9j1b5et7 |   worker  |   registry:5000/dschedule_worker:1.0.0  |   3/3    |
|      -       |     -     |                    -                    | Total: 6 |
+--------------+-----------+-----------------------------------------+----------+

# Error trying to start registry service:
dschedule -s -s registry
[2025-04-28 23:05:08,779][ERROR][swarm,288]: Invalid service name provided: registry
```

5. Balance swarm services:

You can use `--balance` to try and rebalance services within the cluster. It is a best foot forward attept where the
service is reloaded and deployed on a swarm node with the most available resources at the time of reload. If there is
only one node in the cluster you will receive a message indicating to add more nodes to the cluster because a balance
effort cannot be performed.

```bash
dschedule -s -B
[2025-04-28 23:16:39,588][INFO][swarm,246]: Rebalancing swarm services
[2025-04-28 23:16:39,622][INFO][swarm,222]: Reloading broker service
[2025-04-28 23:17:04,911][INFO][swarm,222]: Reloading grafana service
[2025-04-28 23:17:23,768][INFO][swarm,222]: Reloading mongodb_scraper service
[2025-04-28 23:17:42,724][INFO][swarm,222]: Reloading mongodb service
[2025-04-28 23:18:11,866][INFO][swarm,222]: Reloading worker service
[2025-04-28 23:19:28,752][INFO][swarm,222]: Reloading proxy service
[2025-04-28 23:19:47,893][INFO][swarm,222]: Reloading proxy_scraper service
```

# Containers
You can use the `dschedule --container` command to view information about the containers running on the local
swarm node. You can list, prune, get the logs and stats for containers.

1. List containers:
List the local swarm node containers. This is similar to running `docker ps --all` and the list will include containers
that have been stopped or exited which will include containers that were redeployed using the `--reload` option. This is
expected and you can use the `--prune` option to remove exited containers from the list.

```bash
dschedule -c -l
+--------------+-------------------+-------------------------------------------------+-----------------------------+
|      ID      |        Name       |                      Image                      |            Status           |
+--------------+-------------------+-------------------------------------------------+-----------------------------+
| 190876e5730c |      worker.1     |       registry:5000/dschedule_worker:1.0.0      |   Up 10 minutes (healthy)   |
| 5b9483ddc611 |    prometheus.1   |     registry:5000/dschedule_prometheus:1.0.0    |   Up 12 minutes (healthy)   |
| 9f37086bbe6c |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |   Up 12 minutes (healthy)   |
| a761104da59e | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |   Up 12 minutes (healthy)   |
| 7f7186c99a7f |      worker.1     |       registry:5000/dschedule_worker:1.0.0      | Exited (137) 10 minutes ago |
| 65e38b5e3cb6 |     registry.1    |      registry:5000/dschedule_registry:1.0.0     |   Up 24 minutes (healthy)   |
| 2fd15a2fbf51 |    scheduler.1    |     registry:5000/dschedule_scheduler:1.0.0     |   Up 25 minutes (healthy)   |
| 191e580cc958 |      worker.1     |       registry:5000/dschedule_worker:1.0.0      | Exited (137) 14 minutes ago |
| 21e0900e0c03 |     registry.1    |      registry:5000/dschedule_registry:1.0.0     |  Exited (2) 24 minutes ago  |
+--------------+-------------------+-------------------------------------------------+-----------------------------+

# You can use --verbose to pull more information about the containers:
dschedule -c -l -v
{
  "Command": "\"/app/docker-entrypo\u2026\"",
  "CreatedAt": "2025-04-28 23:18:12 +0000 UTC",
  "ID": "190876e5730c",
  "Image": "registry:5000/dschedule_worker:1.0.0",
  "Labels": "com.docker.swarm.task.id=1bemk62ixyn6hkmthl1ejxo1x,com.docker.swarm.task.name=dock-schedule_worker.1.1bemk62ixyn6hkmthl1ejxo1x,com.docker.compose.service=worker,com.docker.compose.version=2.35.1,com.docker.stack.namespace=dock-schedule,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.compose.project=dock-schedule,com.docker.swarm.service.id=dt4x9j1b5et7ifrew7fsbz7fs,com.docker.swarm.service.name=dock-schedule_worker,com.docker.swarm.task=",
  "LocalVolumes": "0",
  "Mounts": "/opt/dock-sche\u2026,/opt/dock-sche\u2026",
  "Names": "dock-schedule_worker.1.1bemk62ixyn6hkmthl1ejxo1x",
  "Networks": "dock-schedule-broker,dock-schedule-job-db",
  "Ports": "",
  "RunningFor": "11 minutes ago",
  "Size": "0B",
  "State": "running",
  "Status": "Up 10 minutes (healthy)"
}
{
  "Command": "\"/custom-entrypoint.\u2026\"",
  "CreatedAt": "2025-04-28 23:16:20 +0000 UTC",
  "ID": "5b9483ddc611",
  "Image": "registry:5000/dschedule_prometheus:1.0.0",
  "Labels": "com.docker.compose.service=prometheus,com.docker.swarm.service.name=dock-schedule_prometheus,com.docker.swarm.task=,org.opencontainers.image.source=https://github.com/prometheus/prometheus,com.docker.swarm.task.id=qqfiklkqxxzgh8xa8uf8v7c5u,com.docker.swarm.task.name=dock-schedule_prometheus.1.qqfiklkqxxzgh8xa8uf8v7c5u,maintainer=The Prometheus Authors <prometheus-developers@googlegroups.com>,com.docker.compose.project=dock-schedule,com.docker.compose.version=2.35.1,com.docker.stack.namespace=dock-schedule,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.service.id=5zrd63gyfu748xdhlotdohz4x",
  "LocalVolumes": "0",
  "Mounts": "/opt/dock-sche\u2026,/var/run/docke\u2026",
  "Names": "dock-schedule_prometheus.1.qqfiklkqxxzgh8xa8uf8v7c5u",
  "Networks": "dock-schedule-proxy",
  "Ports": "9090/tcp",
  "RunningFor": "12 minutes ago",
  "Size": "0B",
  "State": "running",
  "Status": "Up 12 minutes (healthy)"
}
{
  "Command": "\"/custom-entrypoint.\u2026\"",
  "CreatedAt": "2025-04-28 23:16:20 +0000 UTC",
  "ID": "9f37086bbe6c",
  "Image": "registry:5000/dschedule_node_scraper:1.0.0",
  "Labels": "com.docker.swarm.service.name=dock-schedule_node_scraper,com.docker.swarm.task.name=dock-schedule_node_scraper.ak2u8rfw0rvkxats1xdo7ei24.xtpw0a3qrcy3ofk8lqg47zvr8,maintainer=The Prometheus Authors <prometheus-developers@googlegroups.com>,com.docker.stack.namespace=dock-schedule,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.service.id=jgw11cjgi4a9jeltv4n32gofn,com.docker.swarm.task=,com.docker.swarm.task.id=xtpw0a3qrcy3ofk8lqg47zvr8,prometheus-job=node-stats,com.docker.compose.project=dock-schedule,com.docker.compose.service=node_scraper,com.docker.compose.version=2.35.1",
  "LocalVolumes": "0",
  "Mounts": "/proc,/sys,/,/run/udev/data",
  "Names": "dock-schedule_node_scraper.ak2u8rfw0rvkxats1xdo7ei24.xtpw0a3qrcy3ofk8lqg47zvr8",
  "Networks": "dock-schedule-proxy",
  "Ports": "9100/tcp",
  "RunningFor": "12 minutes ago",
  "Size": "0B",
  "State": "running",
  "Status": "Up 12 minutes (healthy)"
}
{
  "Command": "\"/custom-entrypoint.\u2026\"",
  "CreatedAt": "2025-04-28 23:16:20 +0000 UTC",
  "ID": "a761104da59e",
  "Image": "registry:5000/dschedule_container_scraper:1.0.0",
  "Labels": "org.opencontainers.image.title=cadvisor,com.docker.compose.service=container_scraper,com.docker.stack.namespace=dock-schedule,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.service.id=y339xtl38vp9uu79j3h14oc1z,com.docker.swarm.task.id=pgxi8os84zbz41cxzs31nfoj4,com.vmware.cp.artifact.flavor=sha256:c50c90cfd9d12b445b011e6ad529f1ad3daea45c26d20b00732fae3cd71f6a83,org.opencontainers.image.base.name=docker.io/bitnami/minideb:bookworm,org.opencontainers.image.vendor=Broadcom, Inc.,com.docker.compose.version=2.35.1,com.docker.swarm.task=,org.opencontainers.image.description=Application packaged by Broadcom, Inc.,com.docker.swarm.service.name=dock-schedule_container_scraper,com.docker.swarm.task.name=dock-schedule_container_scraper.ak2u8rfw0rvkxats1xdo7ei24.pgxi8os84zbz41cxzs31nfoj4,org.opencontainers.image.created=2025-04-15T10:51:41Z,org.opencontainers.image.ref.name=0.52.1-debian-12-r3,com.docker.compose.project=dock-schedule,org.opencontainers.image.documentation=https://github.com/bitnami/containers/tree/main/bitnami/cadvisor/README.md,org.opencontainers.image.source=https://github.com/bitnami/containers/tree/main/bitnami/cadvisor,org.opencontainers.image.version=0.52.1,prometheus-job=container-stats",
  "LocalVolumes": "0",
  "Mounts": "/dev/disk,/,/sys,/var/lib/docker,/var/run/docke\u2026",
  "Names": "dock-schedule_container_scraper.ak2u8rfw0rvkxats1xdo7ei24.pgxi8os84zbz41cxzs31nfoj4",
  "Networks": "dock-schedule-proxy",
  "Ports": "",
  "RunningFor": "12 minutes ago",
  "Size": "0B",
  "State": "running",
  "Status": "Up 12 minutes (healthy)"
}
{
  "Command": "\"/app/docker-entrypo\u2026\"",
  "CreatedAt": "2025-04-28 23:14:29 +0000 UTC",
  "ID": "7f7186c99a7f",
  "Image": "registry:5000/dschedule_worker:1.0.0",
  "Labels": "com.docker.stack.namespace=dock-schedule,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.service.id=dt4x9j1b5et7ifrew7fsbz7fs,com.docker.swarm.task=,com.docker.swarm.task.id=wlamd094qf07ee7ksdyfrj972,com.docker.compose.project=dock-schedule,com.docker.compose.service=worker,com.docker.swarm.task.name=dock-schedule_worker.1.wlamd094qf07ee7ksdyfrj972,com.docker.compose.version=2.35.1,com.docker.swarm.service.name=dock-schedule_worker",
  "LocalVolumes": "0",
  "Mounts": "/opt/dock-sche\u2026,/opt/dock-sche\u2026",
  "Names": "dock-schedule_worker.1.wlamd094qf07ee7ksdyfrj972",
  "Networks": "dock-schedule-broker,dock-schedule-job-db",
  "Ports": "",
  "RunningFor": "14 minutes ago",
  "Size": "0B",
  "State": "exited",
  "Status": "Exited (137) 10 minutes ago"
}
{
  "Command": "\"/entrypoint.sh /etc\u2026\"",
  "CreatedAt": "2025-04-28 23:04:41 +0000 UTC",
  "ID": "65e38b5e3cb6",
  "Image": "registry:5000/dschedule_registry:1.0.0",
  "Labels": "com.docker.swarm.service.name=dock-schedule_registry,com.docker.swarm.task=,com.docker.swarm.task.id=7uivcu6z0brydz1lafo3e665p,com.docker.compose.version=2.35.1,com.docker.stack.namespace=dock-schedule,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.task.name=dock-schedule_registry.1.7uivcu6z0brydz1lafo3e665p,com.docker.compose.project=registry,com.docker.compose.service=registry,com.docker.swarm.service.id=nysr2eody3wmjvmpcn672vsj3",
  "LocalVolumes": "0",
  "Mounts": "/opt/dock-sche\u2026",
  "Names": "dock-schedule_registry.1.7uivcu6z0brydz1lafo3e665p",
  "Networks": "dock-schedule_default,ingress",
  "Ports": "5000/tcp",
  "RunningFor": "24 minutes ago",
  "Size": "0B",
  "State": "running",
  "Status": "Up 24 minutes (healthy)"
}
{
  "Command": "\"/app/docker-entrypo\u2026\"",
  "CreatedAt": "2025-04-28 23:03:59 +0000 UTC",
  "ID": "2fd15a2fbf51",
  "Image": "registry:5000/dschedule_scheduler:1.0.0",
  "Labels": "com.docker.compose.version=2.35.1,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.task=,com.docker.swarm.task.id=weggj7j7b6mealfych52fgcw8,com.docker.swarm.task.name=dock-schedule_scheduler.1.weggj7j7b6mealfych52fgcw8,com.docker.compose.project=dock-schedule,com.docker.compose.service=scheduler,com.docker.stack.namespace=dock-schedule,com.docker.swarm.service.id=8etd4y9b4n7gx91w3xo7akrcf,com.docker.swarm.service.name=dock-schedule_scheduler",
  "LocalVolumes": "0",
  "Mounts": "/opt/dock-sche\u2026",
  "Names": "dock-schedule_scheduler.1.weggj7j7b6mealfych52fgcw8",
  "Networks": "dock-schedule-broker,dock-schedule-job-db",
  "Ports": "",
  "RunningFor": "25 minutes ago",
  "Size": "0B",
  "State": "running",
  "Status": "Up 25 minutes (healthy)"
}
{
  "Command": "\"/app/docker-entrypo\u2026\"",
  "CreatedAt": "2025-04-28 23:03:59 +0000 UTC",
  "ID": "191e580cc958",
  "Image": "registry:5000/dschedule_worker:1.0.0",
  "Labels": "com.docker.swarm.service.id=dt4x9j1b5et7ifrew7fsbz7fs,com.docker.swarm.service.name=dock-schedule_worker,com.docker.swarm.task.id=iz90su91mfrkzrzeb4qo584q5,com.docker.compose.project=dock-schedule,com.docker.compose.version=2.35.1,com.docker.stack.namespace=dock-schedule,com.docker.swarm.task.name=dock-schedule_worker.1.iz90su91mfrkzrzeb4qo584q5,com.docker.compose.service=worker,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.task=",
  "LocalVolumes": "0",
  "Mounts": "/opt/dock-sche\u2026,/opt/dock-sche\u2026",
  "Names": "dock-schedule_worker.1.iz90su91mfrkzrzeb4qo584q5",
  "Networks": "dock-schedule-broker,dock-schedule-job-db",
  "Ports": "",
  "RunningFor": "25 minutes ago",
  "Size": "0B",
  "State": "exited",
  "Status": "Exited (137) 14 minutes ago"
}
{
  "Command": "\"/entrypoint.sh /etc\u2026\"",
  "CreatedAt": "2025-04-28 22:40:54 +0000 UTC",
  "ID": "21e0900e0c03",
  "Image": "registry:5000/dschedule_registry:1.0.0",
  "Labels": "com.docker.compose.project=registry,com.docker.compose.version=2.35.1,com.docker.swarm.service.id=nysr2eody3wmjvmpcn672vsj3,com.docker.swarm.service.name=dock-schedule_registry,com.docker.swarm.task.id=vhkp1lqi5btutciigrikldmsy,com.docker.compose.service=registry,com.docker.stack.namespace=dock-schedule,com.docker.swarm.node.id=ak2u8rfw0rvkxats1xdo7ei24,com.docker.swarm.task=,com.docker.swarm.task.name=dock-schedule_registry.1.vhkp1lqi5btutciigrikldmsy",
  "LocalVolumes": "0",
  "Mounts": "/opt/dock-sche\u2026",
  "Names": "dock-schedule_registry.1.vhkp1lqi5btutciigrikldmsy",
  "Networks": "dock-schedule_default,ingress",
  "Ports": "",
  "RunningFor": "48 minutes ago",
  "Size": "0B",
  "State": "exited",
  "Status": "Exited (2) 24 minutes ago"
}
```

2. Prune containers:
You can use `--prune` to delete exited containers from the local swarm node.

```bash
dschedule -c -l
+--------------+-------------------+-------------------------------------------------+-----------------------------+
|      ID      |        Name       |                      Image                      |            Status           |
+--------------+-------------------+-------------------------------------------------+-----------------------------+
| 190876e5730c |      worker.1     |       registry:5000/dschedule_worker:1.0.0      |   Up 10 minutes (healthy)   |
| 5b9483ddc611 |    prometheus.1   |     registry:5000/dschedule_prometheus:1.0.0    |   Up 12 minutes (healthy)   |
| 9f37086bbe6c |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |   Up 12 minutes (healthy)   |
| a761104da59e | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |   Up 12 minutes (healthy)   |
| 7f7186c99a7f |      worker.1     |       registry:5000/dschedule_worker:1.0.0      | Exited (137) 10 minutes ago |
| 65e38b5e3cb6 |     registry.1    |      registry:5000/dschedule_registry:1.0.0     |   Up 24 minutes (healthy)   |
| 2fd15a2fbf51 |    scheduler.1    |     registry:5000/dschedule_scheduler:1.0.0     |   Up 25 minutes (healthy)   |
| 191e580cc958 |      worker.1     |       registry:5000/dschedule_worker:1.0.0      | Exited (137) 14 minutes ago |
| 21e0900e0c03 |     registry.1    |      registry:5000/dschedule_registry:1.0.0     |  Exited (2) 24 minutes ago  |
+--------------+-------------------+-------------------------------------------------+-----------------------------+

dschedule -c -p
[2025-04-28 23:34:13,010][INFO][swarm,469]: Pruning containers

dschedule -c -l
+--------------+-------------------+-------------------------------------------------+-------------------------+
|      ID      |        Name       |                      Image                      |          Status         |
+--------------+-------------------+-------------------------------------------------+-------------------------+
| 190876e5730c |      worker.1     |       registry:5000/dschedule_worker:1.0.0      | Up 15 minutes (healthy) |
| 5b9483ddc611 |    prometheus.1   |     registry:5000/dschedule_prometheus:1.0.0    | Up 17 minutes (healthy) |
| 9f37086bbe6c |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   | Up 17 minutes (healthy) |
| a761104da59e | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 | Up 17 minutes (healthy) |
| 65e38b5e3cb6 |     registry.1    |      registry:5000/dschedule_registry:1.0.0     | Up 29 minutes (healthy) |
| 2fd15a2fbf51 |    scheduler.1    |     registry:5000/dschedule_scheduler:1.0.0     | Up 30 minutes (healthy) |
+--------------+-------------------+-------------------------------------------------+-------------------------+
```

3. Get Container stats:
You can use the `--stats` option to get the container stats for a specific container or you can use the `--all` option
to get stats for all containers on the local swarm node. The verbose option has no effect at this time.


```bash
dschedule -c -s worker.1
{
  "BlockIO": "4.1kB / 782kB",
  "CPUPerc": "0.00%",
  "Container": "190876e5730c",
  "ID": "190876e5730c",
  "MemPerc": "1.72%",
  "MemUsage": "30.61MiB / 1.733GiB",
  "Name": "dock-schedule_worker.1.1bemk62ixyn6hkmthl1ejxo1x",
  "NetIO": "29.8kB / 20.7kB",
  "PIDs": "2"
}

# all containers:
dschedule -c -s all
{
  "BlockIO": "4.1kB / 782kB",
  "CPUPerc": "0.01%",
  "Container": "190876e5730c",
  "ID": "190876e5730c",
  "MemPerc": "1.73%",
  "MemUsage": "30.61MiB / 1.733GiB",
  "Name": "dock-schedule_worker.1.1bemk62ixyn6hkmthl1ejxo1x",
  "NetIO": "32.7kB / 22.5kB",
  "PIDs": "2"
}
{
  "BlockIO": "496kB / 8.01MB",
  "CPUPerc": "0.00%",
  "Container": "5b9483ddc611",
  "ID": "5b9483ddc611",
  "MemPerc": "9.53%",
  "MemUsage": "169MiB / 1.733GiB",
  "Name": "dock-schedule_prometheus.1.qqfiklkqxxzgh8xa8uf8v7c5u",
  "NetIO": "41.9MB / 611kB",
  "PIDs": "8"
}
{
  "BlockIO": "131kB / 12.3kB",
  "CPUPerc": "0.01%",
  "Container": "9f37086bbe6c",
  "ID": "9f37086bbe6c",
  "MemPerc": "0.64%",
  "MemUsage": "11.32MiB / 1.733GiB",
  "Name": "dock-schedule_node_scraper.ak2u8rfw0rvkxats1xdo7ei24.xtpw0a3qrcy3ofk8lqg47zvr8",
  "NetIO": "123kB / 1.47MB",
  "PIDs": "4"
}
{
  "BlockIO": "0B / 12.3kB",
  "CPUPerc": "2.01%",
  "Container": "a761104da59e",
  "ID": "a761104da59e",
  "MemPerc": "4.14%",
  "MemUsage": "73.46MiB / 1.733GiB",
  "Name": "dock-schedule_container_scraper.ak2u8rfw0rvkxats1xdo7ei24.pgxi8os84zbz41cxzs31nfoj4",
  "NetIO": "217kB / 10.2MB",
  "PIDs": "11"
}
{
  "BlockIO": "889kB / 0B",
  "CPUPerc": "0.87%",
  "Container": "65e38b5e3cb6",
  "ID": "65e38b5e3cb6",
  "MemPerc": "0.84%",
  "MemUsage": "14.88MiB / 1.733GiB",
  "Name": "dock-schedule_registry.1.7uivcu6z0brydz1lafo3e665p",
  "NetIO": "57.7kB / 154kB",
  "PIDs": "5"
}
{
  "BlockIO": "262kB / 770kB",
  "CPUPerc": "0.13%",
  "Container": "2fd15a2fbf51",
  "ID": "2fd15a2fbf51",
  "MemPerc": "1.64%",
  "MemUsage": "29.12MiB / 1.733GiB",
  "Name": "dock-schedule_scheduler.1.weggj7j7b6mealfych52fgcw8",
  "NetIO": "274kB / 194kB",
  "PIDs": "5"
}
```

4. Get container logs:
You can use either `--logs` or `--watch` to get the logs for a specific container. The `--logs` option will get the
current log and output to console. The `--watch` option will do the same, but stream any new entries to the console
until interrupted via ctrl+c.

```bash
dschedule -c -L worker.1
[2025-04-28 23:18:25,822][INFO][worker,374]: Starting broker
[2025-04-28 23:18:25,822][INFO][worker,221]: Connecting to message broker
[2025-04-28 23:18:25,838][INFO][worker,231]: Successfully connected to broker
[2025-04-28 23:18:25,839][INFO][worker,244]: Successfully opened channel
[2025-04-28 23:18:25,839][INFO][worker,253]: Successfully set exchange
[2025-04-28 23:18:25,839][INFO][worker,265]: Starting to consume messages from queue
[2025-04-28 23:18:26,022][INFO][worker,152]: Successfully set queue

dschedule -c -w proxy.1
----
10.0.1.6 - - [28/Apr/2025:23:42:19 +0000] "GET /metrics?host=mongodb_scraper HTTP/1.1" 200 67288 "-" "Prometheus/3.3.0"
10.0.1.6 - - [28/Apr/2025:23:42:20 +0000] "GET /metrics?ip=10.0.1.15 HTTP/1.1" 200 128686 "-" "Prometheus/3.3.0"
10.0.1.6 - - [28/Apr/2025:23:42:21 +0000] "GET /metrics?ip=10.0.1.17 HTTP/1.1" 200 134796 "-" "Prometheus/3.3.0"
10.0.1.6 - - [28/Apr/2025:23:42:23 +0000] "GET /metrics?ip=10.0.1.5 HTTP/1.1" 200 15049 "-" "Prometheus/3.3.0"
10.0.1.6 - - [28/Apr/2025:23:42:28 +0000] "GET /metrics?ip=10.0.1.3 HTTP/1.1" 200 14926 "-" "Prometheus/3.3.0
....
```


# Jobs

Create cron Job
```bash
dschedule -j -c -n Python-Test01 -t python3 -r test.py -a 0 -f hour -i 1 
[2025-04-26 16:06:17,987][INFO][utils,343]: Job Python-Test01 created successfully

dschedule -j -l
Job Schedule:
[
  {
    "_id": "69112dee-97d0-47a9-9a5d-b63e3f15e51c",
    "name": "Python-Test01",
    "type": "python3",
    "run": "test.py",
    "args": [
      "0"
    ],
    "frequency": "hour",
    "interval": 1,
    "at": null,
    "timezone": "UTC",
    "hostInventory": null,
    "extraVars": null,
    "disabled": false
  }
]

```

Run Job manually:
You can manually run jobs using the `--run` option. This will create a new job and send it to the scheduler. The scheduler
probes the manual jobs every 5 seconds so there may be a delay in the job execution especially if the job queue is
already backlogged. You can wait for the job to complete using the `--wait` option of desired. You can select to run
a predefined cron job using the `--id` options and providing the the job cron ID to run. You can also specify the job
parameters for the manual run similar to creating a cron job using the `--create` minus the frequency the job should
run.

Command Options:
```bash
dschedule -j -r -h
usage: dschedule [-h] [-i ID] [-n NAME] [-t {python3,ansible,bash,php,node}] [-r RUN]
                 [-a ARGS [ARGS ...]] [-H HOSTINVENTORY] [-e EXTRAVARS] [-w]

Dock Schedule: Run Job

options:
  -h, --help            show this help message and exit

  -i ID, --id ID        ID of the cron job to run if you want to run a predefined job

  -n NAME, --name NAME  Name to use for the job run. Default: manual-<type>-<run> (example: manual-
                        python3-hello.py)

  -t {python3,ansible,bash,php,node}, --type {python3,ansible,bash,php,node}
                        Job type to run. Will use predefined if "--id" is used. Options: python3,
                        ansible, bash, php, node

  -r RUN, --run RUN     Job file to run. Will use predefined if "--id" is used. This should be
                        located: /opt/dock-schedule/jobs/<type>/<run> for python3, bash, php, or
                        node type. /opt/dock-schedule/ansible/playbooks/<run> for ansible type

  -a ARGS [ARGS ...], --args ARGS [ARGS ...]
                        Arguments to pass to the python3, bash, php or node script arg parser
                        (example: "--arg1 value1", "--arg2 value2"). Will override predefined if "--
                        id" is used

  -H HOSTINVENTORY, --hostInventory HOSTINVENTORY
                        Host inventory to run remote ansible job on. Requires key=value pairs
                        separated by comma: "hostname1=ip1, hostname2=ip2". Will override predefined
                        if "--id" is used. Use "None" to remove and use worker localhost.

  -e EXTRAVARS, --extraVars EXTRAVARS
                        Extra vars to pass to the ansible job. Requires key=value pairs separated by
                        comma. "var1=value1, var2=value2". Will override predefined if "--id" is
                        used.

  -w, --wait            Wait for the job to finish before returning. Default: False
```


```bash
# Drop --wait, -w to run job in background
dschedule -j -r -i 69112dee-97d0-47a9-9a5d-b63e3f15e51c -w
[2025-04-26 16:16:00,720][INFO][utils,597]: Job Python-Test01 sent to scheduler successfully. Waiting for completion...
[2025-04-26 16:16:15,726][INFO][utils,564]: Job completed successfully

# Change run args:
dschedule -j -r -i 69112dee-97d0-47a9-9a5d-b63e3f15e51c -w -a 1
[2025-04-26 16:17:47,608][INFO][utils,597]: Job Python-Test01 sent to scheduler successfully. Waiting for completion...
[2025-04-26 16:18:02,616][ERROR][utils,567]: Job failed: Task 'Run Job' failed on host 'localhost': non-zero return code

# Python test job
dschedule -j -r -t python3 -r test.py -a 0 -w
[2025-04-26 17:03:04,663][INFO][utils,601]: Job manual-python3-test.py sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:03:09,669][INFO][utils,564]: Job completed successfully

dschedule -j -r -t python3 -r test.py -a 1 -w
[2025-04-26 17:03:20,693][INFO][utils,601]: Job manual-python3-test.py sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:03:25,699][ERROR][utils,567]: Job failed: Task 'Run Job' failed on host 'localhost': non-zero return code

# Php test job
dschedule -j -r -t php -r test.php -a 0 -w
[2025-04-26 17:04:10,244][INFO][utils,601]: Job manual-php-test.php sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:04:15,250][INFO][utils,564]: Job completed successfully

dschedule -j -r -t php -r test.php -a 1 -w
[2025-04-26 17:04:18,848][INFO][utils,601]: Job manual-php-test.php sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:04:23,853][ERROR][utils,567]: Job failed: Task 'Run Job' failed on host 'localhost': non-zero return code

# Bash test job
dschedule -j -r -t bash -r test.sh -a 0 -w
[2025-04-26 17:04:39,596][INFO][utils,601]: Job manual-bash-test.sh sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:04:44,601][INFO][utils,564]: Job completed successfully

dschedule -j -r -t bash -r test.sh -a 1 -w
[2025-04-26 17:04:46,892][INFO][utils,601]: Job manual-bash-test.sh sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:04:51,898][ERROR][utils,567]: Job failed: Task 'Run Job' failed on host 'localhost': non-zero return code

# Node/JS test bob
dschedule -j -r -t node -r test.js -a 0 -w
[2025-04-26 17:06:44,474][INFO][utils,601]: Job manual-node-test.js sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:06:49,477][INFO][utils,564]: Job completed successfully

dschedule -j -r -t node -r test.js -a 1 -w
[2025-04-26 17:06:52,151][INFO][utils,601]: Job manual-node-test.js sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:06:57,154][ERROR][utils,567]: Job failed: Task 'Run Job' failed on host 'localhost': non-zero return code

# Ansible test job
dschedule -j -r -t ansible -r test.yml -e exit_code=0 -w
[2025-04-26 17:38:27,305][INFO][utils,601]: Job manual-ansible-test.yml sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:38:32,307][INFO][utils,564]: Job completed successfully

dschedule -j -r -t ansible -r test.yml -e exit_code=1 -w
[2025-04-26 17:27:24,828][INFO][utils,601]: Job manual-ansible-test.yml sent to scheduler successfully. Waiting for completion...
[2025-04-26 17:27:29,830][ERROR][utils,567]: Job failed: Task 'Fail if exit_code is not 0' failed on host 'localhost': Invalid exit code: 1
```
