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
firewalld and opens up the required NFS and Docker ports, builds the docker images, pushes the images to the swarm
registry and then starts the swarm stack services.

The generated ansible private ssh key is `/opt/dock-schedule/ansible/.env/.ansible_rsa`. Ansible is used to configure
new nodes added to the swarm cluster. You will need the ansible public key
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
currently running container once the new container is in a healthy state. You can use `all` to reload all
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
  "Networks": "dock-schedule-broker,dock-schedule-mongodb",
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
  "Networks": "dock-schedule-broker,dock-schedule-mongodb",
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
  "Networks": "dock-schedule-broker,dock-schedule-mongodb",
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
  "Networks": "dock-schedule-broker,dock-schedule-mongodb",
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
You can use the `--stats` option to get the container stats for a specific container or you can use `all` to get stats
for all containers on the local swarm node. The verbose option has no effect at this time.


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

You can use the `--jobs` option to manage jobs. It includes the functionality to list, create, delete, and update
scheduled jobs as well as get the results of jobs and run jobs manually with specified parameters.

Command Options:
```bash
dschedule -j -h
usage: dschedule [-h] [-l] [-g ...] [-c ...] [-D DELETE] [-u ...] [-r ...] [-R ...] [-T]

Dock Schedule: Jobs

options:
  -h, --help            show this help message and exit

  -l, --list            List dock-schedule job schedule

  -g ..., --get ...     Get dock-schedule job schedule

  -c ..., --create ...  Create a dock-schedule job cron

  -D DELETE, --delete DELETE
                        Delete a dock-schedule job cron (specify job ID)

  -u ..., --update ...  Update a dock-schedule job cron

  -r ..., --run ...     Run a dock-schedule job (specify job name)

  -R ..., --results ...
                        Get the results of dock-schedule jobs

  -T, --timezones       List all timezones available for dock-schedule jobs
```

1. Create cron Job

You can create a cron job by using the `--create` option with the required parameters `--name`, `--type`, `--run`,
`--frequency`, `--interval` or `--at`. The `interval` option will run the job every x frequency while the `at` option
will run the job at a set time based on the frequency provided. `Interval` is based on when the scheduler service
started and `at` is more percises on when it should run. You can use `--timezone` to specify the time to run the job
with the `at` method. `--run` is the actual script or playbook to run and should be located on the export directory
under either jobs/<type> or ansible/playbooks. The `--type` is the interpreter to use as well as the parent directory
of the script or playbook. The `--args` options is used to pass arguments to the job script (not ansible playbook).
Use `extraVars` to pass key-value pairs to the ansible playbook if `--type` is ansible. Use `--hostInventory` to run
the ansible playbook on remote hosts or omit to run the job on the worker locally. The remote hosts must have the
ansible public ssh key assigned to user ansible authorized keys as mentioned earlier. You can create a job that is
disabled by using the `--disabled` option. Then you can enable it later by using the `--update` option.

Every job type (python3, ansible, bash, php, node) has a test job created for you to test job successes and failures.
You can use `--timezones` to list all timezones available for the `--at` option.


Create Options:
```bash
dschedule -j -c -h
usage: dschedule [-h] -n NAME -t {python3,ansible,bash,php,node} -r RUN [-a ARGS [ARGS ...]] -f
                 {second,minute,hour,day} [-i INTERVAL] [-A AT] [-T TIMEZONE] [-H HOSTINVENTORY]
                 [-e EXTRAVARS] [-d]

Dock Schedule: Create Job Cron

options:
  -h, --help            show this help message and exit

  -n NAME, --name NAME  Name of the job to create. Required to create a job cron

  -t {python3,ansible,bash,php,node}, --type {python3,ansible,bash,php,node}
                        Type of the job to create. Options: python3, ansible, bash, php, node

  -r RUN, --run RUN     Name of script or playbook to run for the job. This should be located:
                        /opt/dock-schedule/jobs/<type>/<run> for python3, bash, php, or node type.
                        /opt/dock-schedule/ansible/playbooks/<run> for ansible type

  -a ARGS [ARGS ...], --args ARGS [ARGS ...]
                        Arguments to pass to the python3, bash, php or node script arg parser
                        (example: "--arg1 value1", "--arg2 value2").

  -f {second,minute,hour,day}, --frequency {second,minute,hour,day}
                        Frequency to run the job. Options: second, minute, hour, day

  -i INTERVAL, --interval INTERVAL
                        Interval to run the job based on the frequency. Must set either interval or
                        at, but not both. "at" will take precedence. Options: second frequency:
                        1-infinity, minute frequency: 1-infinity, hour frequency: 1-infinity, day
                        frequency: 1-infinity

  -A AT, --at AT        The time to run the job based on the frequency. Must set either interval or
                        at, but not both. "at" will take precedence. Options: minute frequency:
                        ":SS", hour frequency: "MM:SS" or ":MM", day frequency: "HH:MM:SS" or
                        "HH:MM"

  -T TIMEZONE, --timezone TIMEZONE
                        Timezone to run the job. Used in junction with "at". Default: UTC

  -H HOSTINVENTORY, --hostInventory HOSTINVENTORY
                        Host inventory to run remote ansible job on. Requires key=value pairs
                        separated by comma: "hostname1=ip1, hostname2=ip2". Leave empty for the
                        ansible job to run locally on the worker

  -e EXTRAVARS, --extraVars EXTRAVARS
                        Extra vars to pass to the ansible job. Requires key=value pairs separated by
                        comma. "var1=value1, var2=value2". These will be directly used in the
                        ansible playbook

  -d, --disabled        If the job is disabled. This will cause the job to not run until it is
                        enabled. Default: False
```

```bash
# Create python test job that run every hour with arg '0' (success):
dschedule -j -c -n Python-Test01 -t python3 -r test.py -a 0 -f hour -i 1 
[2025-04-26 16:06:17,987][INFO][utils,343]: Job Python-Test01 created successfully

# Create bash test job that runs every hour at the 30 min mark with arg '0' (success):
dschedule -j -c -n Bash-Test01 -t bash -r test.sh -a 0 -f hour -A :30
[2025-04-29 14:45:02,768][INFO][schedule,104]: Job Bash-Test01 created successfully

# Create PHP test job that runs every day at 13:45 UTC with arg '1' (failure):
dschedule -j -c -n PHP-Test01 -t php -r test.php -a 1 -f day -A 13:45
[2025-04-29 14:47:53,406][INFO][schedule,104]: Job PHP-Test01 created successfully

# Create JS test job that runs every day at 06:15 EST with arg '1' (failure):
dschedule -j -c -n JS-Test01 -t node -r test.js -a 1 -f day -A 06:15 -T EST
[2025-04-29 14:56:24,754][INFO][schedule,104]: Job JS-Test01 created successfully

# Create ansible job that runs every minute with exit_code=0 (success):
dschedule -j -c -n Ansible-Test01 -t ansible -r test.yml -f minute -i 5 -e exit_code=0
[2025-04-29 14:58:58,791][INFO][schedule,104]: Job Ansible-Test01 created successfully

```

2. List job scheduls/crons:

```bash
dschedule -j -l
Job Schedule:
[
  {
    "_id": "adf98018-5e91-4040-8b89-4e118eb8f2e5",
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
  },
  {
    "_id": "5ed41df4-1cd5-45b9-8567-1b8c85dba088",
    "name": "Bash-Test01",
    "type": "bash",
    "run": "test.sh",
    "args": [
      "0"
    ],
    "frequency": "hour",
    "interval": null,
    "at": ":30",
    "timezone": "UTC",
    "hostInventory": null,
    "extraVars": null,
    "disabled": false
  },
  {
    "_id": "bb9314a1-43a6-4c6c-89a6-887cbb47a770",
    "name": "PHP-Test01",
    "type": "php",
    "run": "test.php",
    "args": [
      "1"
    ],
    "frequency": "day",
    "interval": null,
    "at": "13:45",
    "timezone": "UTC",
    "hostInventory": null,
    "extraVars": null,
    "disabled": false
  },
  {
    "_id": "ead27b8d-a22f-4aa5-bc1b-73ccda7ca5b1",
    "name": "JS-Test01",
    "type": "node",
    "run": "test.js",
    "args": [
      "1"
    ],
    "frequency": "day",
    "interval": null,
    "at": "06:15",
    "timezone": "EST",
    "hostInventory": null,
    "extraVars": null,
    "disabled": false
  },
  {
    "_id": "af579395-1693-49b7-bf0d-a18c62773cbb",
    "name": "Ansible-Test01",
    "type": "ansible",
    "run": "test.yml",
    "args": null,
    "frequency": "minute",
    "interval": 5,
    "at": null,
    "timezone": "UTC",
    "hostInventory": {},
    "extraVars": {
      "exit_code": "0"
    },
    "disabled": false
  }
]
```

You can also use the `--get` option to get a specific job cron by name or ID. You can give multiple crons the same name
but each must have a unique ID.

```bash
dschedule -j -g -n Ansible-Test01
Job Schedule:
[
  {
    "_id": "af579395-1693-49b7-bf0d-a18c62773cbb",
    "name": "Ansible-Test01",
    "type": "ansible",
    "run": "test.yml",
    "args": null,
    "frequency": "minute",
    "interval": 10,
    "at": null,
    "timezone": "UTC",
    "hostInventory": {},
    "extraVars": {
      "exit_code": "0"
    },
    "disabled": false
  }
]

# Two jobs with the same name
dschedule -j -g -n Python-Test01
Job Schedule:
[
  {
    "_id": "adf98018-5e91-4040-8b89-4e118eb8f2e5",
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
  },
  {
    "_id": "6781d9a2-a369-43f7-a7a0-a7e6ff962eab",
    "name": "Python-Test01",
    "type": "python3",
    "run": "test.py",
    "args": [
      "0"
    ],
    "frequency": "minute",
    "interval": 30,
    "at": null,
    "timezone": "UTC",
    "hostInventory": null,
    "extraVars": null,
    "disabled": false
  }
]

# Get by ID:
dschedule -j -g -i 6781d9a2-a369-43f7-a7a0-a7e6ff962eab
Job Schedule:
{
  "_id": "6781d9a2-a369-43f7-a7a0-a7e6ff962eab",
  "name": "Python-Test01",
  "type": "python3",
  "run": "test.py",
  "args": [
    "0"
  ],
  "frequency": "minute",
  "interval": 30,
  "at": null,
  "timezone": "UTC",
  "hostInventory": null,
  "extraVars": null,
  "disabled": false
}
```

3. Delete job schedule/cron:

```bash
# Delete JS-Test01
dschedule -j -D ead27b8d-a22f-4aa5-bc1b-73ccda7ca5b1
[2025-04-29 15:03:34,094][INFO][schedule,201]: Successfully deleted job ID ead27b8d-a22f-4aa5-bc1b-73ccda7ca5b1

dschedule -j -l
Job Schedule:
[
  {
    "_id": "adf98018-5e91-4040-8b89-4e118eb8f2e5",
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
  },
  {
    "_id": "5ed41df4-1cd5-45b9-8567-1b8c85dba088",
    "name": "Bash-Test01",
    "type": "bash",
    "run": "test.sh",
    "args": [
      "0"
    ],
    "frequency": "hour",
    "interval": null,
    "at": ":30",
    "timezone": "UTC",
    "hostInventory": null,
    "extraVars": null,
    "disabled": false
  },
  {
    "_id": "bb9314a1-43a6-4c6c-89a6-887cbb47a770",
    "name": "PHP-Test01",
    "type": "php",
    "run": "test.php",
    "args": [
      "1"
    ],
    "frequency": "day",
    "interval": null,
    "at": "13:45",
    "timezone": "UTC",
    "hostInventory": null,
    "extraVars": null,
    "disabled": false
  },
  {
    "_id": "af579395-1693-49b7-bf0d-a18c62773cbb",
    "name": "Ansible-Test01",
    "type": "ansible",
    "run": "test.yml",
    "args": null,
    "frequency": "minute",
    "interval": 5,
    "at": null,
    "timezone": "UTC",
    "hostInventory": {},
    "extraVars": {
      "exit_code": "0"
    },
    "disabled": false
  }
]
```

4. Update job schedule/cron:


Command options:
```bash
dschedule -j -u -h
usage: dschedule [-h] -j JOBID [-n NAME] [-t {python3,ansible,bash,php,node,None}] [-r RUN]
                 [-a ARGS [ARGS ...]] [-f {second,minute,hour,day,None}] [-i INTERVAL] [-A AT]
                 [-T TIMEZONE] [-H HOSTINVENTORY] [-e EXTRAVARS] [-s {enabled,disabled,None}]

Dock Schedule: Update Job Cron

options:
  -h, --help            show this help message and exit

  -j JOBID, --jobID JOBID
                        Job ID of the job to update. Required to update a job cron

  -n NAME, --name NAME  New name for the cron job

  -t {python3,ansible,bash,php,node,None}, --type {python3,ansible,bash,php,node,None}
                        Job type update. Options: python3, ansible, bash, php, node

  -r RUN, --run RUN     Job file to run. This should be located: /opt/dock-
                        schedule/jobs/<type>/<run> for python3, bash, php, or node type. /opt/dock-
                        schedule/ansible/playbooks/<run> for ansible type

  -a ARGS [ARGS ...], --args ARGS [ARGS ...]
                        Arguments to pass to the python3, bash, php or node script arg parser
                        (example: "--arg1 value1", "--arg2 value2"). Include all args and not just
                        the updated ones. Use "NONE" to remove all args.

  -f {second,minute,hour,day,None}, --frequency {second,minute,hour,day,None}
                        Frequency to run the job. Options: second, minute, hour, day

  -i INTERVAL, --interval INTERVAL
                        Interval to run the job based on the frequency. Must set either interval or
                        at, but not both. "at" will take precedence. Options: second frequency:
                        1-infinity, minute frequency: 1-infinity, hour frequency: 1-infinity, day
                        frequency: 1-infinity. Use "None" to remove.

  -A AT, --at AT        The time to run the job based on the frequency. Must set either interval or
                        at, but not both. "at" will take precedence. Options: minute frequency:
                        ":SS", hour frequency: "MM:SS" or ":MM", day frequency: "HH:MM:SS" or
                        "HH:MM". Use "None" to remove.

  -T TIMEZONE, --timezone TIMEZONE
                        Timezone to run the job. Used in junction with "at"

  -H HOSTINVENTORY, --hostInventory HOSTINVENTORY
                        Host inventory to run remote ansible job on. Requires key=value pairs
                        separated by comma: "hostname1=ip1, hostname2=ip2". Use "None" to remove and
                        use localhost.

  -e EXTRAVARS, --extraVars EXTRAVARS
                        Extra vars to pass to the ansible job. Requires key=value pairs separated by
                        comma. "var1=value1, var2=value2". Include all expected key values and not
                        just the updated ones

  -s {enabled,disabled,None}, --state {enabled,disabled,None}
                        State of the cron job. Options: enabled, disabled
```

```bash
# Disable a job:
dschedule -j -u -j 6781d9a2-a369-43f7-a7a0-a7e6ff962eab -s disabled
[2025-04-29 15:20:33,512][INFO][schedule,259]: Successfully updated job ID 6781d9a2-a369-43f7-a7a0-a7e6ff962eab

dschedule -j -g -i 6781d9a2-a369-43f7-a7a0-a7e6ff962eab
Job Schedule:
{
  "_id": "6781d9a2-a369-43f7-a7a0-a7e6ff962eab",
  "name": "Python-Test01",
  "type": "python3",
  "run": "test.py",
  "args": [
    "0"
  ],
  "frequency": "minute",
  "interval": 30,
  "at": null,
  "timezone": "UTC",
  "hostInventory": null,
  "extraVars": null,
  "disabled": true
}

# update the frequency and interval to run two hours from every 30 minutes:
dschedule -j -u -j 6781d9a2-a369-43f7-a7a0-a7e6ff962eab -f hour -i 2
[2025-04-29 15:22:35,986][INFO][schedule,259]: Successfully updated job ID 6781d9a2-a369-43f7-a7a0-a7e6ff962eab

dschedule -j -g -i 6781d9a2-a369-43f7-a7a0-a7e6ff962eab
Job Schedule:
{
  "_id": "6781d9a2-a369-43f7-a7a0-a7e6ff962eab",
  "name": "Python-Test01",
  "type": "python3",
  "run": "test.py",
  "args": [
    "0"
  ],
  "frequency": "hour",
  "interval": 2,
  "at": null,
  "timezone": "UTC",
  "hostInventory": null,
  "extraVars": null,
  "disabled": true
}


# Update to run every day at 12:42 EST
dschedule -j -u -j 6781d9a2-a369-43f7-a7a0-a7e6ff962eab -f day -A 12:42 -i None -T EST
[2025-04-29 15:25:52,372][INFO][schedule,259]: Successfully updated job ID 6781d9a2-a369-43f7-a7a0-a7e6ff962eab

dschedule -j -g -i 6781d9a2-a369-43f7-a7a0-a7e6ff962eab
Job Schedule:
{
  "_id": "6781d9a2-a369-43f7-a7a0-a7e6ff962eab",
  "name": "Python-Test01",
  "type": "python3",
  "run": "test.py",
  "args": [
    "0"
  ],
  "frequency": "day",
  "interval": null,
  "at": "12:42",
  "timezone": "EST",
  "hostInventory": null,
  "extraVars": null,
  "disabled": true
}

# update the name, type, run, args and state to enabled:
dschedule -j -u -j 6781d9a2-a369-43f7-a7a0-a7e6ff962eab -n NewName -t bash -r test.sh -a 1 -s enabled
[2025-04-29 15:33:16,744][INFO][schedule,259]: Successfully updated job ID 6781d9a2-a369-43f7-a7a0-a7e6ff962eab

dschedule -j -g -i 6781d9a2-a369-43f7-a7a0-a7e6ff962eab
Job Schedule:
{
  "_id": "6781d9a2-a369-43f7-a7a0-a7e6ff962eab",
  "name": "NewName",
  "type": "bash",
  "run": "test.sh",
  "args": [
    "1"
  ],
  "frequency": "day",
  "interval": null,
  "at": "12:42",
  "timezone": "EST",
  "hostInventory": null,
  "extraVars": null,
  "disabled": false
}

# Update ansible host inventory and extra vars:
dschedule -j -u -j af579395-1693-49b7-bf0d-a18c62773cbb -e exit_code=1 -H node1=192.168.6.2,node2=192.168.6.3
[2025-04-29 15:35:49,129][INFO][schedule,259]: Successfully updated job ID af579395-1693-49b7-bf0d-a18c62773cbb

dschedule -j -g -i af579395-1693-49b7-bf0d-a18c62773cbb
Job Schedule:
{
  "_id": "af579395-1693-49b7-bf0d-a18c62773cbb",
  "name": "Ansible-Test01",
  "type": "ansible",
  "run": "test.yml",
  "args": null,
  "frequency": "minute",
  "interval": 10,
  "at": null,
  "timezone": "UTC",
  "hostInventory": {
    "node1": "192.168.6.2",
    "node2": "192.168.6.3"
  },
  "extraVars": {
    "exit_code": "1"
  },
  "disabled": false
}
```

5. Run job manually:

You can manually run jobs using the `--run` option. This will create a new job and send it to the scheduler. The scheduler
probes the manual jobs every 5 seconds so there may be a delay in the job execution especially if the job queue is
already backlogged. You can wait for the job to complete using the `--wait` option if desired. You can select to run
a predefined cron job using the `--id` option and providing the the job ID to run. You can also specify the job
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

1. Run Local Jobs (on worker containers in the swarm):
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


2. Run Remote Jobs (on remote ansible hosts):
```bash

```

6. Results

You can use the `--results` option to pull job result data as well as get the backlog of pending jobs to help you
determine if you need to scale your workers. You can either use `--id` to get a specific job result or `--name` to get
all jobs that have run with the given name. Use `all` with `--name` to get all jobs that have run. Use `--limit` to
limit the returned result quantity. You can also use `--filter` to filter job results by job status. Success will give
you all jobs that have exited with a 0 exit code. Failed will give you all jobs that have exited with a non-zero exit
code. Scheduled will give you all jobs sitting in the queue waiting for a worker to acknowledge the job. Use `--verbose`
to get more detailed output of the job results. The job results are stored in the database and will be autodeleted after
7 days.


```bash
Commands Options:
```bash
dschedule -j -R -h
usage: dschedule [-h] [-i ID] [-n NAME] [-l LIMIT] [-f {success,failed,scheduled}] [-v]

Dock Schedule: Run Job

options:
  -h, --help            show this help message and exit

  -i ID, --id ID        ID of the job to get results for

  -n NAME, --name NAME  Job name to query. Use "all" to get all jobs.

  -l LIMIT, --limit LIMIT
                        Limit the number of job results to return. Default: 10

  -f {success,failed,scheduled}, --filter {success,failed,scheduled}
                        Filter the job results by status. Options: success, failed, scheduled

  -v, --verbose         Enable verbose output
```

```bash
# get the results of the last 15 jobs that have run:
dschedule -j -R -n all -l 15
ID: 208947c9-b239-40e6-b430-76aae2efc0d6, Name: Bash-Test01, State: completed, Result: True, Duration: 725 ms

ID: 61d032f2-011e-44fb-8be3-2167ce61e26f, Name: Python-Test01, State: completed, Result: True, Duration: 756 ms

ID: 666e06c9-483d-4631-9c93-10c0cb2dc7f7, Name: Bash-Test01, State: completed, Result: True, Duration: 749 ms

ID: 95681059-1c8b-435d-bbd0-7cee793d1d33, Name: Bash-Test01, State: completed, Result: True, Duration: 721 ms

ID: b5050bd7-1165-4078-9e7f-fc9b5925522d, Name: Python-Test01, State: completed, Result: True, Duration: 734 ms

ID: ed70c33d-d465-47f9-b97a-233588029b7b, Name: Bash-Test01, State: completed, Result: True, Duration: 626 ms

ID: d5778bb4-fb8a-496b-9e9d-9a3faf2a6366, Name: Python-Test01, State: completed, Result: True, Duration: 681 ms

ID: 4c8ae96f-9226-4338-97cf-6fbaeed35abc, Name: Python-Test01, State: completed, Result: True, Duration: 695 ms

ID: c3b1a345-17d3-4725-8726-7778282135c4, Name: Ansible-Test01, State: completed, Result: False, Duration: 542 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1

ID: a13df419-d368-4b74-a491-ba4c29c6c090, Name: Ansible-Test01, State: completed, Result: False, Duration: 473 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1

ID: 68c844b7-fe5e-4e7b-9c70-ef3d4c80acdc, Name: Bash-Test01, State: completed, Result: True, Duration: 677 ms

ID: 42f4385b-65a3-4b40-811d-a461713b54ba, Name: Ansible-Test01, State: completed, Result: False, Duration: 520 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1

ID: 49840eb6-b275-49c5-a001-3df1fd1941c4, Name: Python-Test01, State: completed, Result: True, Duration: 753 ms

ID: 62947b78-ab89-47ae-90d3-0c4469759606, Name: Ansible-Test01, State: completed, Result: False, Duration: 509 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1

ID: 8566559a-34aa-4572-b4df-bab966501179, Name: Ansible-Test01, State: completed, Result: False, Duration: 506 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1


# Verbose output example of last 5 jobs run:
dschedule -j -R -n all -v -l 5
Job Results:
[
  {
    "_id": "d64f1b4a-84f0-4889-a7c7-06ad8afc9843",
    "name": "Bash-Test01",
    "type": "bash",
    "run": "test.sh",
    "args": [
      "0"
    ],
    "hostInventory": null,
    "extraVars": {
      "script_file": "test.sh",
      "script_type": "bash",
      "script_args": [
        "0"
      ]
    },
    "state": "completed",
    "scheduled": "2025-04-29T20:11:42.205442",
    "start": "2025-04-29T20:11:43.444000",
    "end": "2025-04-29T20:11:44.133000",
    "result": true,
    "error": null,
    "expiryTime": "2025-05-06T20:11:42.205000"
  },
  {
    "_id": "4dedc3ac-dfc9-45db-a14c-c6ed6792c66a",
    "name": "Python-Test01",
    "type": "python3",
    "run": "test.py",
    "args": [
      "0"
    ],
    "hostInventory": null,
    "extraVars": {
      "script_file": "test.py",
      "script_type": "python3",
      "script_args": [
        "0"
      ]
    },
    "state": "completed",
    "scheduled": "2025-04-29T20:11:42.201615",
    "start": "2025-04-29T20:11:42.675000",
    "end": "2025-04-29T20:11:43.439000",
    "result": true,
    "error": null,
    "expiryTime": "2025-05-06T20:11:42.204000"
  },
  {
    "_id": "2c964aa9-0360-4061-9ce4-b67277e07104",
    "name": "Ansible-Test01",
    "type": "ansible",
    "run": "test.yml",
    "args": null,
    "hostInventory": {
      "node1": "192.168.6.2",
      "node2": "192.168.6.3"
    },
    "extraVars": {
      "exit_code": "1"
    },
    "state": "completed",
    "scheduled": "2025-04-29T20:11:42.198720",
    "start": "2025-04-29T20:11:42.204000",
    "end": "2025-04-29T20:11:42.667000",
    "result": false,
    "error": "Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1",
    "expiryTime": "2025-05-06T20:11:42.199000"
  },
  {
    "_id": "3435270c-64a2-47b3-9bd3-ff0846e7acad",
    "name": "Bash-Test01",
    "type": "bash",
    "run": "test.sh",
    "args": [
      "0"
    ],
    "hostInventory": null,
    "extraVars": {
      "script_file": "test.sh",
      "script_type": "bash",
      "script_args": [
        "0"
      ]
    },
    "state": "completed",
    "scheduled": "2025-04-29T20:06:42.009045",
    "start": "2025-04-29T20:06:42.701000",
    "end": "2025-04-29T20:06:43.383000",
    "result": true,
    "error": null,
    "expiryTime": "2025-05-06T20:06:42.010000"
  },
  {
    "_id": "d0d0a66b-300a-47fa-978f-fa115d02c2b1",
    "name": "Python-Test01",
    "type": "python3",
    "run": "test.py",
    "args": [
      "0"
    ],
    "hostInventory": null,
    "extraVars": {
      "script_file": "test.py",
      "script_type": "python3",
      "script_args": [
        "0"
      ]
    },
    "state": "completed",
    "scheduled": "2025-04-29T20:06:42.005947",
    "start": "2025-04-29T20:06:42.012000",
    "end": "2025-04-29T20:06:42.695000",
    "result": true,
    "error": null,
    "expiryTime": "2025-05-06T20:06:42.006000"
  }
]

# get last three results of a named job:
dschedule -j -R -n Python-Test01 -l 3
ID: 15d6ae12-d9e8-4fa4-969c-1b9bd5f770e0, Name: Python-Test01, State: completed, Result: True, Duration: 677 ms

ID: 4dedc3ac-dfc9-45db-a14c-c6ed6792c66a, Name: Python-Test01, State: completed, Result: True, Duration: 764 ms

ID: d0d0a66b-300a-47fa-978f-fa115d02c2b1, Name: Python-Test01, State: completed, Result: True, Duration: 683 ms

# get details results a specific job:
dschedule -j -R -i 15d6ae12-d9e8-4fa4-969c-1b9bd5f770e0 -v
Job Results:
[
  {
    "_id": "15d6ae12-d9e8-4fa4-969c-1b9bd5f770e0",
    "name": "Python-Test01",
    "type": "python3",
    "run": "test.py",
    "args": [
      "0"
    ],
    "hostInventory": null,
    "extraVars": {
      "script_file": "test.py",
      "script_type": "python3",
      "script_args": [
        "0"
      ]
    },
    "state": "completed",
    "scheduled": "2025-04-29T20:16:42.386141",
    "start": "2025-04-29T20:16:42.394000",
    "end": "2025-04-29T20:16:43.071000",
    "result": true,
    "error": null,
    "expiryTime": "2025-05-06T20:16:42.386000"
  }
]

# Get the last 3 failed jobs:
dschedule -j -R -n all -f failed -l 3
ID: 2c964aa9-0360-4061-9ce4-b67277e07104, Name: Ansible-Test01, State: completed, Result: False, Duration: 463 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1

ID: c3b1a345-17d3-4725-8726-7778282135c4, Name: Ansible-Test01, State: completed, Result: False, Duration: 542 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1

ID: a13df419-d368-4b74-a491-ba4c29c6c090, Name: Ansible-Test01, State: completed, Result: False, Duration: 473 ms
  Error: Task 'Fail if exit_code is not 0' failed on host 'node1': Invalid exit code: 1

# Get the last 3 success jobs:
dschedule -j -R -n all -f success -l 3
ID: 84f19ebe-c85b-45d7-b1e7-8bda8b087410, Name: Bash-Test01, State: completed, Result: True, Duration: 646 ms

ID: 15d6ae12-d9e8-4fa4-969c-1b9bd5f770e0, Name: Python-Test01, State: completed, Result: True, Duration: 677 ms

ID: d64f1b4a-84f0-4889-a7c7-06ad8afc9843, Name: Bash-Test01, State: completed, Result: True, Duration: 689 ms

# Get the scheduled jobs (10 results by default, but more might be pending, use -l to get full list):
dschedule -j -R -n all -f scheduled
ID: 97df3b00-ad79-4540-90a1-e7763d0ea684, Name: Bash-Test01, State: pending, Result: None, Duration: N/A

ID: 8d7aea68-8c8e-4fcc-b1d7-8a42965f1e64, Name: Python-Test01, State: pending, Result: None, Duration: N/A

ID: cd080228-9e29-405c-becb-6766e1e0cbcc, Name: Bash-Test01, State: pending, Result: None, Duration: N/A

ID: 009ca495-7434-4f40-a2a2-884efabd0fd7, Name: Python-Test01, State: pending, Result: None, Duration: N/A

ID: 8039f6e6-c01e-409c-b8c9-b758fbc16d25, Name: Bash-Test01, State: pending, Result: None, Duration: N/A

ID: 6677a58b-86d1-489d-a3ff-1e439352bf36, Name: Python-Test01, State: pending, Result: None, Duration: N/A

ID: 1eeab812-7127-42e7-afeb-98bc78299138, Name: Bash-Test01, State: pending, Result: None, Duration: N/A

ID: 7a4daaae-160c-4096-9d9d-a27d98fe12a8, Name: Python-Test01, State: pending, Result: None, Duration: N/A

ID: 9cbaf507-9ef7-4f9b-a9f4-9a49f5c4515a, Name: Bash-Test01, State: pending, Result: None, Duration: N/A

ID: 9e363af0-c7dd-4929-960c-ac51d062ebc9, Name: Python-Test01, State: pending, Result: None, Duration: N/A
# This is a good indicator that you need to scale your workers to handle the job load
```

7. Available Timezones to schedule jobs:

The available timezones are the same as pytzm but you can list them for a quick reference using `--timezones`

```bash
dschedule -j -T
Timezone Options:
[
  "Africa/Abidjan",
  "Africa/Accra",
  "Africa/Addis_Ababa",
  "Africa/Algiers",
  "Africa/Asmara",
  "Africa/Asmera",
  "Africa/Bamako",
  "Africa/Bangui",
  "Africa/Banjul",
  "Africa/Bissau",
  "Africa/Blantyre",
  "Africa/Brazzaville",
  "Africa/Bujumbura",
  "Africa/Cairo",
  "Africa/Casablanca",
  "Africa/Ceuta",
  "Africa/Conakry",
  "Africa/Dakar",
  "Africa/Dar_es_Salaam",
  "Africa/Djibouti",
  "Africa/Douala",
  "Africa/El_Aaiun",
  "Africa/Freetown",
  "Africa/Gaborone",
  "Africa/Harare",
  "Africa/Johannesburg",
  "Africa/Juba",
  "Africa/Kampala",
  "Africa/Khartoum",
  "Africa/Kigali",
  "Africa/Kinshasa",
  "Africa/Lagos",
  "Africa/Libreville",
  "Africa/Lome",
  "Africa/Luanda",
  "Africa/Lubumbashi",
  "Africa/Lusaka",
  "Africa/Malabo",
  "Africa/Maputo",
  "Africa/Maseru",
  "Africa/Mbabane",
  "Africa/Mogadishu",
  "Africa/Monrovia",
  "Africa/Nairobi",
  "Africa/Ndjamena",
  "Africa/Niamey",
  "Africa/Nouakchott",
  "Africa/Ouagadougou",
  "Africa/Porto-Novo",
  "Africa/Sao_Tome",
  "Africa/Timbuktu",
  "Africa/Tripoli",
  "Africa/Tunis",
  "Africa/Windhoek",
  "America/Adak",
  "America/Anchorage",
  "America/Anguilla",
  "America/Antigua",
  "America/Araguaina",
  "America/Argentina/Buenos_Aires",
  "America/Argentina/Catamarca",
  "America/Argentina/ComodRivadavia",
  "America/Argentina/Cordoba",
  "America/Argentina/Jujuy",
  "America/Argentina/La_Rioja",
  "America/Argentina/Mendoza",
  "America/Argentina/Rio_Gallegos",
  "America/Argentina/Salta",
  "America/Argentina/San_Juan",
  "America/Argentina/San_Luis",
  "America/Argentina/Tucuman",
  "America/Argentina/Ushuaia",
  "America/Aruba",
  "America/Asuncion",
  "America/Atikokan",
  "America/Atka",
  "America/Bahia",
  "America/Bahia_Banderas",
  "America/Barbados",
  "America/Belem",
  "America/Belize",
  "America/Blanc-Sablon",
  "America/Boa_Vista",
  "America/Bogota",
  "America/Boise",
  "America/Buenos_Aires",
  "America/Cambridge_Bay",
  "America/Campo_Grande",
  "America/Cancun",
  "America/Caracas",
  "America/Catamarca",
  "America/Cayenne",
  "America/Cayman",
  "America/Chicago",
  "America/Chihuahua",
  "America/Ciudad_Juarez",
  "America/Coral_Harbour",
  "America/Cordoba",
  "America/Costa_Rica",
  "America/Coyhaique",
  "America/Creston",
  "America/Cuiaba",
  "America/Curacao",
  "America/Danmarkshavn",
  "America/Dawson",
  "America/Dawson_Creek",
  "America/Denver",
  "America/Detroit",
  "America/Dominica",
  "America/Edmonton",
  "America/Eirunepe",
  "America/El_Salvador",
  "America/Ensenada",
  "America/Fort_Nelson",
  "America/Fort_Wayne",
  "America/Fortaleza",
  "America/Glace_Bay",
  "America/Godthab",
  "America/Goose_Bay",
  "America/Grand_Turk",
  "America/Grenada",
  "America/Guadeloupe",
  "America/Guatemala",
  "America/Guayaquil",
  "America/Guyana",
  "America/Halifax",
  "America/Havana",
  "America/Hermosillo",
  "America/Indiana/Indianapolis",
  "America/Indiana/Knox",
  "America/Indiana/Marengo",
  "America/Indiana/Petersburg",
  "America/Indiana/Tell_City",
  "America/Indiana/Vevay",
  "America/Indiana/Vincennes",
  "America/Indiana/Winamac",
  "America/Indianapolis",
  "America/Inuvik",
  "America/Iqaluit",
  "America/Jamaica",
  "America/Jujuy",
  "America/Juneau",
  "America/Kentucky/Louisville",
  "America/Kentucky/Monticello",
  "America/Knox_IN",
  "America/Kralendijk",
  "America/La_Paz",
  "America/Lima",
  "America/Los_Angeles",
  "America/Louisville",
  "America/Lower_Princes",
  "America/Maceio",
  "America/Managua",
  "America/Manaus",
  "America/Marigot",
  "America/Martinique",
  "America/Matamoros",
  "America/Mazatlan",
  "America/Mendoza",
  "America/Menominee",
  "America/Merida",
  "America/Metlakatla",
  "America/Mexico_City",
  "America/Miquelon",
  "America/Moncton",
  "America/Monterrey",
  "America/Montevideo",
  "America/Montreal",
  "America/Montserrat",
  "America/Nassau",
  "America/New_York",
  "America/Nipigon",
  "America/Nome",
  "America/Noronha",
  "America/North_Dakota/Beulah",
  "America/North_Dakota/Center",
  "America/North_Dakota/New_Salem",
  "America/Nuuk",
  "America/Ojinaga",
  "America/Panama",
  "America/Pangnirtung",
  "America/Paramaribo",
  "America/Phoenix",
  "America/Port-au-Prince",
  "America/Port_of_Spain",
  "America/Porto_Acre",
  "America/Porto_Velho",
  "America/Puerto_Rico",
  "America/Punta_Arenas",
  "America/Rainy_River",
  "America/Rankin_Inlet",
  "America/Recife",
  "America/Regina",
  "America/Resolute",
  "America/Rio_Branco",
  "America/Rosario",
  "America/Santa_Isabel",
  "America/Santarem",
  "America/Santiago",
  "America/Santo_Domingo",
  "America/Sao_Paulo",
  "America/Scoresbysund",
  "America/Shiprock",
  "America/Sitka",
  "America/St_Barthelemy",
  "America/St_Johns",
  "America/St_Kitts",
  "America/St_Lucia",
  "America/St_Thomas",
  "America/St_Vincent",
  "America/Swift_Current",
  "America/Tegucigalpa",
  "America/Thule",
  "America/Thunder_Bay",
  "America/Tijuana",
  "America/Toronto",
  "America/Tortola",
  "America/Vancouver",
  "America/Virgin",
  "America/Whitehorse",
  "America/Winnipeg",
  "America/Yakutat",
  "America/Yellowknife",
  "Antarctica/Casey",
  "Antarctica/Davis",
  "Antarctica/DumontDUrville",
  "Antarctica/Macquarie",
  "Antarctica/Mawson",
  "Antarctica/McMurdo",
  "Antarctica/Palmer",
  "Antarctica/Rothera",
  "Antarctica/South_Pole",
  "Antarctica/Syowa",
  "Antarctica/Troll",
  "Antarctica/Vostok",
  "Arctic/Longyearbyen",
  "Asia/Aden",
  "Asia/Almaty",
  "Asia/Amman",
  "Asia/Anadyr",
  "Asia/Aqtau",
  "Asia/Aqtobe",
  "Asia/Ashgabat",
  "Asia/Ashkhabad",
  "Asia/Atyrau",
  "Asia/Baghdad",
  "Asia/Bahrain",
  "Asia/Baku",
  "Asia/Bangkok",
  "Asia/Barnaul",
  "Asia/Beirut",
  "Asia/Bishkek",
  "Asia/Brunei",
  "Asia/Calcutta",
  "Asia/Chita",
  "Asia/Choibalsan",
  "Asia/Chongqing",
  "Asia/Chungking",
  "Asia/Colombo",
  "Asia/Dacca",
  "Asia/Damascus",
  "Asia/Dhaka",
  "Asia/Dili",
  "Asia/Dubai",
  "Asia/Dushanbe",
  "Asia/Famagusta",
  "Asia/Gaza",
  "Asia/Harbin",
  "Asia/Hebron",
  "Asia/Ho_Chi_Minh",
  "Asia/Hong_Kong",
  "Asia/Hovd",
  "Asia/Irkutsk",
  "Asia/Istanbul",
  "Asia/Jakarta",
  "Asia/Jayapura",
  "Asia/Jerusalem",
  "Asia/Kabul",
  "Asia/Kamchatka",
  "Asia/Karachi",
  "Asia/Kashgar",
  "Asia/Kathmandu",
  "Asia/Katmandu",
  "Asia/Khandyga",
  "Asia/Kolkata",
  "Asia/Krasnoyarsk",
  "Asia/Kuala_Lumpur",
  "Asia/Kuching",
  "Asia/Kuwait",
  "Asia/Macao",
  "Asia/Macau",
  "Asia/Magadan",
  "Asia/Makassar",
  "Asia/Manila",
  "Asia/Muscat",
  "Asia/Nicosia",
  "Asia/Novokuznetsk",
  "Asia/Novosibirsk",
  "Asia/Omsk",
  "Asia/Oral",
  "Asia/Phnom_Penh",
  "Asia/Pontianak",
  "Asia/Pyongyang",
  "Asia/Qatar",
  "Asia/Qostanay",
  "Asia/Qyzylorda",
  "Asia/Rangoon",
  "Asia/Riyadh",
  "Asia/Saigon",
  "Asia/Sakhalin",
  "Asia/Samarkand",
  "Asia/Seoul",
  "Asia/Shanghai",
  "Asia/Singapore",
  "Asia/Srednekolymsk",
  "Asia/Taipei",
  "Asia/Tashkent",
  "Asia/Tbilisi",
  "Asia/Tehran",
  "Asia/Tel_Aviv",
  "Asia/Thimbu",
  "Asia/Thimphu",
  "Asia/Tokyo",
  "Asia/Tomsk",
  "Asia/Ujung_Pandang",
  "Asia/Ulaanbaatar",
  "Asia/Ulan_Bator",
  "Asia/Urumqi",
  "Asia/Ust-Nera",
  "Asia/Vientiane",
  "Asia/Vladivostok",
  "Asia/Yakutsk",
  "Asia/Yangon",
  "Asia/Yekaterinburg",
  "Asia/Yerevan",
  "Atlantic/Azores",
  "Atlantic/Bermuda",
  "Atlantic/Canary",
  "Atlantic/Cape_Verde",
  "Atlantic/Faeroe",
  "Atlantic/Faroe",
  "Atlantic/Jan_Mayen",
  "Atlantic/Madeira",
  "Atlantic/Reykjavik",
  "Atlantic/South_Georgia",
  "Atlantic/St_Helena",
  "Atlantic/Stanley",
  "Australia/ACT",
  "Australia/Adelaide",
  "Australia/Brisbane",
  "Australia/Broken_Hill",
  "Australia/Canberra",
  "Australia/Currie",
  "Australia/Darwin",
  "Australia/Eucla",
  "Australia/Hobart",
  "Australia/LHI",
  "Australia/Lindeman",
  "Australia/Lord_Howe",
  "Australia/Melbourne",
  "Australia/NSW",
  "Australia/North",
  "Australia/Perth",
  "Australia/Queensland",
  "Australia/South",
  "Australia/Sydney",
  "Australia/Tasmania",
  "Australia/Victoria",
  "Australia/West",
  "Australia/Yancowinna",
  "Brazil/Acre",
  "Brazil/DeNoronha",
  "Brazil/East",
  "Brazil/West",
  "CET",
  "CST6CDT",
  "Canada/Atlantic",
  "Canada/Central",
  "Canada/Eastern",
  "Canada/Mountain",
  "Canada/Newfoundland",
  "Canada/Pacific",
  "Canada/Saskatchewan",
  "Canada/Yukon",
  "Chile/Continental",
  "Chile/EasterIsland",
  "Cuba",
  "EET",
  "EST",
  "EST5EDT",
  "Egypt",
  "Eire",
  "Etc/GMT",
  "Etc/GMT+0",
  "Etc/GMT+1",
  "Etc/GMT+10",
  "Etc/GMT+11",
  "Etc/GMT+12",
  "Etc/GMT+2",
  "Etc/GMT+3",
  "Etc/GMT+4",
  "Etc/GMT+5",
  "Etc/GMT+6",
  "Etc/GMT+7",
  "Etc/GMT+8",
  "Etc/GMT+9",
  "Etc/GMT-0",
  "Etc/GMT-1",
  "Etc/GMT-10",
  "Etc/GMT-11",
  "Etc/GMT-12",
  "Etc/GMT-13",
  "Etc/GMT-14",
  "Etc/GMT-2",
  "Etc/GMT-3",
  "Etc/GMT-4",
  "Etc/GMT-5",
  "Etc/GMT-6",
  "Etc/GMT-7",
  "Etc/GMT-8",
  "Etc/GMT-9",
  "Etc/GMT0",
  "Etc/Greenwich",
  "Etc/UCT",
  "Etc/UTC",
  "Etc/Universal",
  "Etc/Zulu",
  "Europe/Amsterdam",
  "Europe/Andorra",
  "Europe/Astrakhan",
  "Europe/Athens",
  "Europe/Belfast",
  "Europe/Belgrade",
  "Europe/Berlin",
  "Europe/Bratislava",
  "Europe/Brussels",
  "Europe/Bucharest",
  "Europe/Budapest",
  "Europe/Busingen",
  "Europe/Chisinau",
  "Europe/Copenhagen",
  "Europe/Dublin",
  "Europe/Gibraltar",
  "Europe/Guernsey",
  "Europe/Helsinki",
  "Europe/Isle_of_Man",
  "Europe/Istanbul",
  "Europe/Jersey",
  "Europe/Kaliningrad",
  "Europe/Kiev",
  "Europe/Kirov",
  "Europe/Kyiv",
  "Europe/Lisbon",
  "Europe/Ljubljana",
  "Europe/London",
  "Europe/Luxembourg",
  "Europe/Madrid",
  "Europe/Malta",
  "Europe/Mariehamn",
  "Europe/Minsk",
  "Europe/Monaco",
  "Europe/Moscow",
  "Europe/Nicosia",
  "Europe/Oslo",
  "Europe/Paris",
  "Europe/Podgorica",
  "Europe/Prague",
  "Europe/Riga",
  "Europe/Rome",
  "Europe/Samara",
  "Europe/San_Marino",
  "Europe/Sarajevo",
  "Europe/Saratov",
  "Europe/Simferopol",
  "Europe/Skopje",
  "Europe/Sofia",
  "Europe/Stockholm",
  "Europe/Tallinn",
  "Europe/Tirane",
  "Europe/Tiraspol",
  "Europe/Ulyanovsk",
  "Europe/Uzhgorod",
  "Europe/Vaduz",
  "Europe/Vatican",
  "Europe/Vienna",
  "Europe/Vilnius",
  "Europe/Volgograd",
  "Europe/Warsaw",
  "Europe/Zagreb",
  "Europe/Zaporozhye",
  "Europe/Zurich",
  "GB",
  "GB-Eire",
  "GMT",
  "GMT+0",
  "GMT-0",
  "GMT0",
  "Greenwich",
  "HST",
  "Hongkong",
  "Iceland",
  "Indian/Antananarivo",
  "Indian/Chagos",
  "Indian/Christmas",
  "Indian/Cocos",
  "Indian/Comoro",
  "Indian/Kerguelen",
  "Indian/Mahe",
  "Indian/Maldives",
  "Indian/Mauritius",
  "Indian/Mayotte",
  "Indian/Reunion",
  "Iran",
  "Israel",
  "Jamaica",
  "Japan",
  "Kwajalein",
  "Libya",
  "MET",
  "MST",
  "MST7MDT",
  "Mexico/BajaNorte",
  "Mexico/BajaSur",
  "Mexico/General",
  "NZ",
  "NZ-CHAT",
  "Navajo",
  "PRC",
  "PST8PDT",
  "Pacific/Apia",
  "Pacific/Auckland",
  "Pacific/Bougainville",
  "Pacific/Chatham",
  "Pacific/Chuuk",
  "Pacific/Easter",
  "Pacific/Efate",
  "Pacific/Enderbury",
  "Pacific/Fakaofo",
  "Pacific/Fiji",
  "Pacific/Funafuti",
  "Pacific/Galapagos",
  "Pacific/Gambier",
  "Pacific/Guadalcanal",
  "Pacific/Guam",
  "Pacific/Honolulu",
  "Pacific/Johnston",
  "Pacific/Kanton",
  "Pacific/Kiritimati",
  "Pacific/Kosrae",
  "Pacific/Kwajalein",
  "Pacific/Majuro",
  "Pacific/Marquesas",
  "Pacific/Midway",
  "Pacific/Nauru",
  "Pacific/Niue",
  "Pacific/Norfolk",
  "Pacific/Noumea",
  "Pacific/Pago_Pago",
  "Pacific/Palau",
  "Pacific/Pitcairn",
  "Pacific/Pohnpei",
  "Pacific/Ponape",
  "Pacific/Port_Moresby",
  "Pacific/Rarotonga",
  "Pacific/Saipan",
  "Pacific/Samoa",
  "Pacific/Tahiti",
  "Pacific/Tarawa",
  "Pacific/Tongatapu",
  "Pacific/Truk",
  "Pacific/Wake",
  "Pacific/Wallis",
  "Pacific/Yap",
  "Poland",
  "Portugal",
  "ROC",
  "ROK",
  "Singapore",
  "Turkey",
  "UCT",
  "US/Alaska",
  "US/Aleutian",
  "US/Arizona",
  "US/Central",
  "US/East-Indiana",
  "US/Eastern",
  "US/Hawaii",
  "US/Indiana-Starke",
  "US/Michigan",
  "US/Mountain",
  "US/Pacific",
  "US/Samoa",
  "UTC",
  "Universal",
  "W-SU",
  "WET",
  "Zulu"
]
```

# Workers

The worker service should be the only one in the stack that would require to scale. You can use the `--worker` option
to specifiy the number of workers that should be deployed in the cluster. This will not scale up the cluster to the
quantity provided, but will ensure that number of workers are deployed in the cluster. Meaning, it will also remove
workers if the number is lower than what is currently running.

```bash
dschedule -w 15

dschedule -s -l
+--------------+-------------------+-------------------------------------------------+-----------+
|      ID      |        Name       |                      Image                      |  Replicas |
+--------------+-------------------+-------------------------------------------------+-----------+
| w0xud9ffoxzr |       broker      |       registry:5000/dschedule_broker:1.0.0      |    1/1    |
| y339xtl38vp9 | container_scraper | registry:5000/dschedule_container_scraper:1.0.0 |    3/3    |
| tg8sdt4guogj |      grafana      |      registry:5000/dschedule_grafana:1.0.0      |    1/1    |
| 21oyesaxlaoy |      mongodb      |      registry:5000/dschedule_mongodb:1.0.0      |    1/1    |
| ty6sxstsp70z |  mongodb_scraper  |  registry:5000/dschedule_mongodb_scraper:1.0.0  |    1/1    |
| jgw11cjgi4a9 |    node_scraper   |    registry:5000/dschedule_node_scraper:1.0.0   |    3/3    |
| 5zrd63gyfu74 |     prometheus    |     registry:5000/dschedule_prometheus:1.0.0    |    1/1    |
| 733wfnx4hehw |       proxy       |       registry:5000/dschedule_proxy:1.0.0       |    1/1    |
| szz0gnl4sqdn |   proxy_scraper   |   registry:5000/dschedule_proxy_scraper:1.0.0   |    1/1    |
| nysr2eody3wm |      registry     |      registry:5000/dschedule_registry:1.0.0     |    1/1    |
| twrovw9vnpx4 |     scheduler     |     registry:5000/dschedule_scheduler:1.0.0     |    1/1    |
| dt4x9j1b5et7 |       worker      |       registry:5000/dschedule_worker:1.0.0      |   15/15   |
|      -       |         -         |                        -                        | Total: 30 |
+--------------+-------------------+-------------------------------------------------+-----------+
```

Then of course you can use --swarm --list --verbose to view where the workers are deployed in the cluster:
```bash
dschedule -S -l -v
dock-schedule-1 (192.168.122.110) [Leader]
    CPU Load Avg (1m):    9.0%
    CPU Load Avg (5m):    16.5%
    CPU Load Avg (15m):   13.5%
    Memory Used:          1.48 GiB (85.4%)
    Disk Used:            10.31 GiB (54.7%)
    Containers:
	dock-schedule_broker.1.184opbko5n3rg2kd2ps6vz46p
	    CPU (1m):    0.4%
	    Memory Used: 104.43 MiB (6.9%)
	dock-schedule_container_scraper.ak2u8rfw0rvkxats1xdo7ei24.ekgbtn7p3trf8q27vm1xl44ze
	    CPU (1m):    2.3%
	    Memory Used: 68.75 MiB (4.5%)
	dock-schedule_grafana.1.ps26xk48ms2vxk6qlftuyuov6
	    CPU (1m):    0.2%
	    Memory Used: 112.87 MiB (7.5%)
	dock-schedule_mongodb.1.q4ntrzn4ee40htxtkeuujayfy
	    CPU (1m):    0.5%
	    Memory Used: 174.72 MiB (11.5%)
	dock-schedule_mongodb_scraper.1.uvccgr19858n3eaj7boskezfk
	    CPU (1m):    0.4%
	    Memory Used: 37.73 MiB (2.5%)
	dock-schedule_node_scraper.ak2u8rfw0rvkxats1xdo7ei24.jlslsyase1dna323nfmlzie4a
	    CPU (1m):    0.2%
	    Memory Used: 18.39 MiB (1.2%)
	dock-schedule_prometheus.1.u0xss8late32cbugi4lupy2a4
	    CPU (1m):    0.3%
	    Memory Used: 237.21 MiB (15.7%)
	dock-schedule_proxy.1.8uncvqdyyg2959wzt4w5p2c7b
	    CPU (1m):    0.1%
	    Memory Used: 6.51 MiB (0.4%)
	dock-schedule_proxy_scraper.1.yml2488nwpjlht6moxtblpj69
	    CPU (1m):    0.1%
	    Memory Used: 23.49 MiB (1.6%)
	dock-schedule_worker.1.j2u6zuqrha8yaqt6jk17onucm
	    CPU (1m):    0.9%
	    Memory Used: 54.09 MiB (3.6%)
	dock-schedule_registry.1.ugmcq07xf11ni1kg97h6jrigk
	    CPU (1m):    0.1%
	    Memory Used: 21.64 MiB (1.4%)
	dock-schedule_scheduler.1.m0d9m6h2heha4xb3a169uzhwl
	    CPU (1m):    0.1%
	    Memory Used: 30.80 MiB (2.0%)
	dock-schedule_worker.9.gzkz5ewhsb6ril9293e3j7010
	    CPU (1m):    0.1%
	    Memory Used: 27.89 MiB (1.8%)
	dock-schedule_worker.11.ia9ec2x8dhy7fs5bypwwkzdu2
	    CPU (1m):    0.1%
	    Memory Used: 27.91 MiB (1.8%)
	dock-schedule_worker.4.udxft3se1vs1u6mwistsg6t3a
	    CPU (1m):    0.1%
	    Memory Used: 28.49 MiB (1.9%)
	dock-schedule_worker.8.v3lp6yjn65c6awzkgqtz8flnh
	    CPU (1m):    0.1%
	    Memory Used: 27.98 MiB (1.8%)
dock-schedule-2 (192.168.122.52) 
    CPU Load Avg (1m):    5.0%
    CPU Load Avg (5m):    13.5%
    CPU Load Avg (15m):   9.0%
    Memory Used:          0.75 GiB (43.1%)
    Disk Used:            6.43 GiB (34.1%)
    Containers:
	dock-schedule_container_scraper.tzyvedvj816i7a424jtheeq26.nhx4n7ql20yslomem9ljown03
	    CPU (1m):    1.2%
	    Memory Used: 105.28 MiB (13.8%)
	dock-schedule_node_scraper.tzyvedvj816i7a424jtheeq26.n4hooxsvqlb5816habok50p81
	    CPU (1m):    0.1%
	    Memory Used: 29.15 MiB (3.8%)
	dock-schedule_worker.3.5korygikmeakv84k1rncqda63
	    CPU (1m):    0.8%
	    Memory Used: 48.82 MiB (6.4%)
	dock-schedule_worker.13.9h0ho36r3kjoqaogay9uu23pl
	    CPU (1m):    0.1%
	    Memory Used: 30.27 MiB (4.0%)
	dock-schedule_worker.6.j3jcq9jit11gepb2ql7irmlhw
	    CPU (1m):    0.1%
	    Memory Used: 31.30 MiB (4.1%)
	dock-schedule_worker.7.ke8f739rc6rch1jtxikcuqn27
	    CPU (1m):    0.1%
	    Memory Used: 31.30 MiB (4.1%)
	dock-schedule_worker.14.pemnz2krx2npcna6vgoze9y5c
	    CPU (1m):    0.1%
	    Memory Used: 31.31 MiB (4.1%)
dock-schedule-3 (192.168.122.195) 
    CPU Load Avg (1m):    0.5%
    CPU Load Avg (5m):    4.0%
    CPU Load Avg (15m):   3.5%
    Memory Used:          0.77 GiB (44.3%)
    Disk Used:            6.43 GiB (34.1%)
    Containers:
	dock-schedule_container_scraper.jaj2f3zwj3zcyzz0cpdexy1uh.nvfop9qso9b9bnb1b71h5jami
	    CPU (1m):    1.2%
	    Memory Used: 105.38 MiB (13.4%)
	dock-schedule_node_scraper.jaj2f3zwj3zcyzz0cpdexy1uh.ts6xaw4ihb3l5xmps4xgxu398
	    CPU (1m):    0.1%
	    Memory Used: 29.47 MiB (3.7%)
	dock-schedule_worker.5.rga6hxebon6xxw6e7l9ck2byt
	    CPU (1m):    0.8%
	    Memory Used: 37.78 MiB (4.8%)
	dock-schedule_worker.10.jvq52zx1iq1707me4gs6f4vje
	    CPU (1m):    0.1%
	    Memory Used: 31.46 MiB (4.0%)
	dock-schedule_worker.12.r9n52ojptozrezqrfui30nf7c
	    CPU (1m):    0.1%
	    Memory Used: 31.40 MiB (4.0%)
	dock-schedule_worker.2.um4h3ikqpa0hxwjaexz20udpq
	    CPU (1m):    0.1%
	    Memory Used: 31.24 MiB (4.0%)
	dock-schedule_worker.15.w3v3ud41nswh0ei55js3rmmlv
	    CPU (1m):    0.1%
	    Memory Used: 29.47 MiB (3.7%)
```
