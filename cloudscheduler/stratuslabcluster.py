"""
StratusLab connector - done as part of a Cern summer student project by unknown
student.
"""
import os
import time
import ConfigParser
import threading
import base64
from cloudscheduler import cluster_tools
from stratuslab.ConfigHolder import ConfigHolder
from stratuslab.Runner import Runner
from stratuslab.Exceptions import OneException
import cloudscheduler.utilities as utilities




class StratusLabCluster(cluster_tools.ICluster):

    """
    Connector class for StratusLab Clouds - Has not been tested for years.
    """

    VM_TARGETSTATE = "Running"
    VM_NODES = "1"
    VM_SHUTDOWN = 90.0
    ERROR = 1

    VM_STATES = {
        'INIT'      : 'Starting',
        'BOOT'      : 'Starting',
        'PROLOG'    : 'Starting',
        'PENDING'   : 'Starting',
        'HOLD'      : 'Starting',
        'RUNNING'   : 'Running',
        'ACTIVE'    : 'Running',
        'STOPPED'   : 'Running',
        'SUSPENDED' : 'Running',
        'DONE'      : 'Shutdown',
        'EPILOG'    : 'Shutdown',
        'FAILED'    : 'Error',
        'FAILURE'   : 'Error',
        'UNKNOWN'   : 'Error',
    }
    log = utilities.get_cloudscheduler_logger()
    config = ConfigParser.ConfigParser()
    config_file = os.path.expanduser('~/.stratuslab/stratuslab-user.cfg')
    config_section = 'default'
    config.read(config_file)

    #Read the stratuslab configuration file
    username, password, endpoint = None, None, None

    try:
        username = config.get(config_section, 'username')
    except ConfigParser.NoOptionError:
        log.error("Stratuslab config file %s does not contain username. VM creation will fail", config_file)
    except ConfigParser.NoSectionError:
        log.error("No section '%s' found Stratuslab config file '%s'. \
                  Do the file and section exist? VM creation will fail",
                  config_section, config_file)
    try:
        password = config.get(config_section, 'password')
    except ConfigParser.NoOptionError:
        log.error("Stratuslab config file %s does not contain password. VM creation will fail", config_file)
    except ConfigParser.NoSectionError:
        log.error("No section '%s' found Stratuslab config file '%s'. \
                  Do the file and section exist? VM creation will fail",
                  config_section, config_file)

    try:
        endpoint = config.get(config_section, 'endpoint')
    except ConfigParser.NoOptionError:
        log.error("Stratuslab config file %s does not contain endpoint. VM creation will fail", config_file)
    except ConfigParser.NoSectionError:
        log.error("No section '%s' found Stratuslab config file '%s'. \
                  Do the file and section exist? VM creation will fail",
                  config_section, config_file)

    options = Runner.defaultRunOptions()
    options.update({'username'            : username,
                    'password'            : password,
                    'endpoint'            : endpoint,
                    'marketplaceEndpoint' : 'https://marketplace.stratuslab.eu',
                    'mpi_machine_file'    : True,
                    'cluster_admin'       : 'root',
                    'master_vmid'         : None,
                    'tolerate_failures'   : False,
                    'clean_after_failure' : False,
                    'include_master'      : True,
                    'shared_folder'       :'/home',
                    'add_packages'        : None,
                    'ssh_hostbased'       : True,
                    'verboseLevel'        : 0
                   })
    _v_configHolder = ConfigHolder(options)

    __idMap = {}
    __vmMap = {}


    def __init__(self, name="Dummy StratusLab Cluster", host="localhost", cloud_type="StratusLab",
                 memory=None, max_vm_mem=-1, cpu_archs=None, networks=None, vm_slots=0,
                 cpu_cores=0, storage=0,
                 contextualization='', enabled=True, priority=0,
                 keep_alive=0,):

        # Call super class' init
        cluster_tools.ICluster.__init__(self, name=name, host=host, cloud_type=cloud_type,
                                        memory=memory, max_vm_mem=max_vm_mem,
                                        cpu_archs=cpu_archs, networks=networks, vm_slots=vm_slots,
                                        cpu_cores=cpu_cores, storage=storage, enabled=enabled,
                                        priority=priority, keep_alive=keep_alive,)
        try:
            contex = open(contextualization, 'r')
            strat = contex.read()
            StratusLabCluster._v_configHolder.set('extraContextData', 'EC2_USER_DATA=%s' \
                                                  %base64.standard_b64encode(strat))
        except IOError:
            self.log.error("Contextualization file '%s' is not valid. \
                      Proceeding without contextualization...", str(contextualization))

        self.__runnerIds = {}


    def vm_create(self, vm_name, vm_type="CernVM", vm_user="root", vm_networkassoc="",
                  vm_image="", vm_mem=1, vm_cores=1, vm_storage=30, vm_keepalive=0,
                  myproxy_creds_name=None, myproxy_server=None, myproxy_server_port=None,
                  job_per_core=False, vm_loc=''):

        self.log.debug("Running new instance with Marketplace id %s in StratusLab", str(vm_loc))
        runner = None

        if vm_loc not in StratusLabCluster.__idMap:
            #vm_loc: URL of VM or key? Does not seem to matter in Runner (l.506)
            runner = Runner(vm_loc, StratusLabCluster._v_configHolder)
            StratusLabCluster.__idMap[vm_loc] = runner
        else:
            runner = StratusLabCluster.__idMap[vm_loc]

        try:
            ids = runner.runInstance()
            self.log.debug("Created instances: %s", str(ids))
            #for new_id in ids:
            new_id = ids[len(ids) - 1]
            #if job didnt't set a keep_alive use the clouds default
            if not vm_keepalive and self.keep_alive:
                vm_keepalive = self.keep_alive
            new_vm = cluster_tools.VM(name=vm_name, id=str(new_id), vmtype=vm_type, user=vm_user,
                                      network=vm_networkassoc, image=vm_image, memory=vm_mem,
                                      cpucores=vm_cores, storage=vm_storage,
                                      keep_alive=vm_keepalive,
                                      myproxy_creds_name=myproxy_creds_name,
                                      myproxy_server=myproxy_server,
                                      myproxy_server_port=myproxy_server_port,
                                      job_per_core=job_per_core)

            StratusLabCluster.__vmMap[str(new_id)] = vm_loc

            if vm_loc not in self.__runnerIds:
                self.__runnerIds[vm_loc] = [str(new_id),]
            else:
                self.__runnerIds[vm_loc].append(str(new_id))
            self.vms.append(new_vm)

            try:
                self.resource_checkout(new_vm)
            except:
                self.log.exception("Unexpected error checking out resources when creating a VM."
                                   " Programming error?")
                return self.ERROR
            #endfor
            return 0

        except Exception, e:
            self.log.exception("Exception running new instance in StratusLab: %s", str(e))
            return -1


    def __cleanKill(self, vm, return_resources=True):

        self.log.verbose('Cleaning caches for VM with id %s' % str(vm.id))

        if return_resources and vm.return_resources:
            self.resource_return(vm)

        with self.vms_lock:

            try:
                self.vms.remove(vm)
            except ValueError:
                self.log.exception("Attempted to remove vm from list that was already removed.")

            try:
                self.__runnerIds[StratusLabCluster.__vmMap[vm.id]].remove(vm.id)
            except:
                self.log.verbose("Attempted to remove already removed runner id")

            try:
                del StratusLabCluster.__vmMap[vm.id]
            except:
                self.log.verbose("Attempted to remove already removed VM id")


    def __vm_kill(self, vm, runner, clean=False, return_resources=True):

        self.log.debug("Send kill signal to VM %s in StratusLab", str(vm.id))

        try:
            runner.killInstances([int(vm.id)])
        finally:
            if clean:
                self.__cleanKill(vm, return_resources)


    def vm_destroy(self, vm, return_resources=True, reason=""):

        self.log.debug("Send shutdown signal to VM %s in StratusLab", str(vm.id))

        if len(reason) > 0:
            self.log.debug("Reason: %s", reason)

        try:
            StratusLabCluster.__idMap[StratusLabCluster.__vmMap[vm.id]].shutdownInstances([int(vm.id)])
            thread = threading._Timer(StratusLabCluster.VM_SHUTDOWN, self.__vm_kill,
                                      args=[vm,
                                            StratusLabCluster.__idMap[StratusLabCluster.__vmMap[vm.id]]])
            self.log.debug("Waiting in new thread %s to send kill signal to VM %s in StratusLab",
                           str(StratusLabCluster.VM_SHUTDOWN), str(vm.id))
            thread.start()
            self.__cleanKill(vm, return_resources)
            return 0
        except:
            self.log.exception("VM with id %s shutdown error in StratusLab", str(vm.id))

            try:
                self.__vm_kill(vm, StratusLabCluster.__idMap[StratusLabCluster.__vmMap[vm.id]],
                               clean=True, return_resources=return_resources)
                self.log.debug("Managed to kill VM with id %s in StratusLab", str(vm.id))
                return 0
            except:
                retry = 3
                while retry > 0:
                    self.log.debug("Error sending kill signal to VM with id %s, %s trials remaining. \
                              Retrying...", str(vm.id), str(retry))
                    time.sleep(5)
                    try:
                        self.__vm_kill(vm, StratusLabCluster.__idMap[StratusLabCluster.__vmMap[vm.id]],
                                       clean=True, return_resources=return_resources)
                        self.log.debug("Managed to kill VM with id %s in StratusLab", str(vm.id))
                        return 0
                    except:
                        pass
                    retry -= 1
                self.log.debug("No way, can't destroy VM with id %s in StratusLab. \
                          Maybe already destroyed, cleaning...", str(vm.id))
                self.__cleanKill(vm, False)
                return -1


    def vm_poll(self, vm):

        try:
            with self.vms_lock:
                new_status = self.VM_STATES.\
                    get(StratusLabCluster.__idMap[StratusLabCluster.__vmMap[vm.id]].
                        getVmState(int(vm.id)).upper(), 'Error')
                if vm.status != new_status:
                    vm.last_state_change = int(time.time())
                    self.log.debug("VM: %s on %s. Changed from %s to %s.",
                                   str(vm.id), self.name, vm.status, new_status)
                    vm.status = new_status
                elif vm.override_status != None and new_status:
                    log.debug("New status for VM %s, override status", str(vm.id))
                    vm.override_status = None
                    vm.errorconnect = None

            vm.lastpoll = int(time.time())
            return new_status
        except OneException, e:
            self.log.exception("One exception: %s", str(e))
            return 'shutdown'
        except Exception, e:
            self.log.exception("Unknown exception: %s", str(e))
            return 'unknown'


    def __getstate__(self):

        state = self.__dict__.copy()
        del state['vms_lock']
        del state['res_lock']
        return state


    def __setstate__(self, state):

        self.__dict__ = state
        self.vms_lock = threading.RLock()
        self.res_lock = threading.RLock()
        self.__setRunnerIds(state['_StratusLabCluster__runnerIds'])


    def __setRunnerIds(self, runnerIds):

        self.__runnerIds = runnerIds

        for key in self.__runnerIds.keys():

            if len(self.__runnerIds[key]) > 0:
                run = Runner(key, StratusLabCluster.__configHolder)
                self.__idMap[key] = run

                for runner_id in self.__runnerIds[key]:
                    self.__vmMap[runner_id] = str(key)
                    run.vmIds.append(runner_id)
            else:
                del self.__runnerIds[key]
