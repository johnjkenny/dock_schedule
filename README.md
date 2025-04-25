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
- scheduler: scheduler service for scheduling jobs in the swarm cluster (runs on manager node)
- worker: worker service for executing jobs in the swarm cluster

The proxy service exposes ports `80`, `443`, and `8080`. `80` reroutes to `443` and `443` routes to grafana service UI.
Port `8080` routes to prometheus service UI where you can see the state of the swarm metric scrape jobs as well as run
queries against the data. You can also use `/api/v1/query` URI to query the prometheus API for metrics.

The worker can handle python, bash, php, javascript (npm), and ansible jobs. By default there are three worker replicas
within the swarm cluster. Each worker can queue a total of 3 jobs at a time which means a total of 9 jobs can be
delivered to the swarm workers at a time by default. The message broker service will hold onto the remaining queued jobs
until a worker completes and acknowledges a job. You can view the broker queue in the grafana dashboard which will show you
how many messages (jobs) are waiting to be delivered to the workers. You can increase/decrease the number of worker
replicas based on the backlog of jobs in the queue. Depending on the resources you have available on your swarm manager
node you may also have to increase/decrease the number of swarm nodes within the cluster to handle the load of the
worker demand.


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
```bash
# create a virtual environment:
python3 -m venv venv

# activate the virtual environment:
source venv/bin/activate

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
[2025-04-25 14:56:59,086][INFO][utils,723]: Creating service users
[2025-04-25 14:56:59,434][INFO][utils,747]: Creating swarm directory tree
[2025-04-25 14:56:59,455][INFO][utils,783]: Creating dock-schedule directory tree
[2025-04-25 14:57:25,780][INFO][utils,793]: Initializing certificate store
[2025-04-25 14:57:32,067][INFO][utils,857]: Generating SSL certificates for swarm manager
[2025-04-25 14:57:32,448][INFO][utils,875]: Creating ansible keys
[2025-04-25 14:57:33,054][INFO][utils,899]: Creating docker swarm

PLAY [Create Docker Swarm] *****************************************************

TASK [Gathering Facts] *********************************************************
ok: [localhost]

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

TASK [Build docker images] *****************************************************
changed: [localhost]

TASK [Start Swarm Services] ****************************************************
changed: [localhost]

PLAY RECAP *********************************************************************
localhost                  : ok=35   changed=28   unreachable=0    failed=0    skipped=4    rescued=0    ignored=0   
[2025-04-25 15:03:22,277][INFO][utils,908]: Successfully initialized dock-schedule
```


# Jobs

