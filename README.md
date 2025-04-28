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
localhost                  : ok=38   changed=31   unreachable=0    failed=0    skipped=4    rescued=0    ignored=0   
[2025-04-28 16:42:01,469][INFO][init,212]: Successfully initialized dock-schedule
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
