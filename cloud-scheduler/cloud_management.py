#!/usr/bin/python

## Auth: Duncan Penfold-Brown. 6/15/2009.

## CLOUD MANAGEMENT
##
## The Cluster superclass provides the basic structure for cluster information,
## and provides the framework (interface) for cloud management functionality.
## Each of its subclasses should should correspond to a specific implementation 
## for cloud management functionality. That is, each subclass should implement 
## the functions in the Cluster superclass according to a specific software. 
## Currently, only a Nimbus subclass exists. If support is desired for other 
## cloud solutions, other subclasses (such as an OpenNebula subclass) might 
## also be desired.
##
## To import specific subclasses only, simply alter the cloud_scheduler import lines.
##     e.g.:    from cloud_management import  NimbusCluster
##


##
## Imports
##

from subprocess import Popen
import datetime
import sys
import logging
import string
import nimbus_xml

##
## GLOBALS
##

## Log files
#  TODO: Revise logging issue: vm commands and internal messages in the same log
#  Currently: vm command stdout is dumped to a file, and log msgs are sent to a
#   python log object.

# Create a file to dump vm command outputs in to.
vm_logfile = "vm.log"
vm_log = open(vm_logfile, 'w')

# Create a python logger
nimbus_logfile = "nimbus.log"
logging.basicConfig(level=logging.DEBUG, 
                    format="%(asctime)s - %(levelname)s: %(message)s",
		    filename=nimbus_logfile, 
		    filemode='a')


# A class for storing created VM information. Used to populate Cluster classes
# 'vms' lists.

class VM:

    ## Instance Variables

    ## Instance Methods

    # Constructor
    # name         - (str) The name of the vm (arbitrary)
    # id           - (str) The id tag for the VM. Whatever is used to access the vm
    #              - by cloud software (Nimbus: epr file. OpenNebula: id number, etc.)
    # clusteraddr  - (str) The address of the cluster hosting the VM
    # type         - (str) The cloud type of the VM (Nimbus, OpenNebula, etc)
    # network      - (str) The network association the VM uses
    # cpuarch      - (str) The required CPU architecture of the VM
    # imageloation - (str) The location of the image from which the VM was created
    # memory       - (int) The memory used by the VM
    # mementry     - (int) The index of the entry in the host cluster's memory list
    #                from which this VM is taking memory
    def __init__(self, name, id, clusteraddr, type, network, cpuarch, imagelocation,\
      memory, mementry):
        print "dbg - New VM object created:"
	print "dbg - VM - Name: %s, id: %s, host: %s, image: %s, memory: %d" \
	  % (name, id, clusteraddr, imagelocation, memory)
	self.name = name
	self.id = id
	self.clusteraddr = clusteraddr
	self.type = type
	self.network = network
	self.cpuarch = cpuarch
	self.imagelocation = imagelocation
	self.memory = memory
	self.mementry = mementry

	# Set a status variable on new creation
	self.status = "Starting"

    # Print a short description of the VM
    # spacer - (str) a string to prepend to each VM line being printed
    def print_short(self, spacer):
       print spacer + "VM Name: %s, ID: %s, host: %s, Status: %s" \
         % (self.name, self.id, self.clusteraddr, self.status)

# A simple class for storing a list of Cluster type resources (or Cluster sub-
# classes). Consists of a name and a list.

class ResourcePool:
    
    # Instance variables    
    name = "default"
    resources = []
    
    # Instance methods

    # Constructor
    def __init__(self, name):
        print "dbg - New ResourcePool " + name + " created"
	self.name = name

    # Add a cluster resource to the pool's resource list
    def add_resource(self, cluster):
        self.resources.append(cluster)

    # Print the name+address of every cluster in the resource pool
    def print_pool(self, ):
        print "Resource pool " + self.name + ":"
        if len(self.resources) == 0:
	    print "Pool is empty... Cannot print pool"
	else:
	    for cluster in self.resources:
	        print "\t" + cluster.name + "\t" + cluster.cloud_type + "\t" + \
		  cluster.network_address
    
    # Return an arbitrary resource from the 'resources' list. Does not remove
    # the returned element from the list.
    # (Currently, the first cluster in the list is returned)
    def get_resource(self, ):
	if len(self.resources) == 0:
	    print "Pool is empty... Cannot return resource."
	    return None
	
	return (self.resources[0])
    
    # Return the first resource that fits the passed in VM requirements. Does
    # not remove the element returned.
    # Built to support "First-fit" scheduling.
    # Parameters:
    #    network  - the network assoication required by the VM
    #    cpuarch  - the cpu architecture that the VM must run on
    #    memory   - the amount of memory (RAM) the VM requires
    #    TODO: storage   - the amount of scratch space the VM requires
    # Return: returns a Cluster object if one is found that vits VM requirments
    #         Otherwise, returns the 'None' object
    def get_resourceFF(self, network, cpuarch, memory):
        if len(self.resources) == 0:
	    print "Pool is empty... Cannot return FF resource"
	    return None
	
	for cluster in self.resources:
            # If the cluster has no open VM slots
	    if (cluster.vm_slots <= 0)
	        continue
	    # If the cluster has no sufficient memory entries for the VM
	    if (cluster.find_mementry(memory) < 0)
	        continue
	    # If the cluster does not have the required CPU architecture
	    if not (cpuarch in cluster.cpu_archs)
                continue
	    # If required network is NOT in cluster's network associations
	    if not (network in cluster.network_pools):
	        continue
	    
	    # Return the cluster as an available resource (meets all job reqs)
	    return cluster
	
	# If no clusters are found (no clusters can host the required VM)
	return None


# The Cluster superclass, containing all general cluster instance variables
# and Cluster interface methods (stubs for implementation in subclasses).

class Cluster:
   
    ## Instance variables (preset to defaults)
    name            = 'default-cluster'
    network_address = '0.0.0.0'
    cloud_type      = 'default-type'
    vm_slots        = 0
    cpu_cores       = 0
    storageGB       = 0
    
    # A list of the memory available on each cluster worker node
    memory = []
    # A list of the network pools made available to VMs
    network_pools = []
    # A list of the available CPU architectures on the cluster
    cpu_archs = []
    
    # Running vms list (uses best-effort internal representation of resources)
    vms = []

    ## Instance methods

    # Constructor
    def __init__(self, ):
        print "dbg - New Cluster created"

    # Set Cluster attributes from a parameter list
    def populate(self, attr_list):
        (self.name, self.network_address, self.cloud_type, self.vm_slots, self.cpu_cores, \
          self.storageGB, memory, cpu_archs, network_pools) = attr_list;
        
	# Strip the newline from the last config line item (network_pools string)
        network_pools = network_pools.rstrip("\n")

	# Split strings into lists for list fields (memory, cpuarchs, networkpools)
	self.memory = memory.split(",")
	self.cpu_archs = cpu_archs.split(",")
	self.network_pools = network_pools.split(",")
	
	# Convert numerical fields to ints
        self.vm_slots = int(self.vm_slots)
	self.cpu_cores = int(self.cpu_cores)
	self.storageGB = int(self.storageGB)
	# Set all self.memory values to ints (iterate through memory list)
	for i in range(len(self.memory)):
	    self.memory[i] = int(self.memory[i])
	    
        print "dbg - Cluster populated successfully"
        
    # Print cluster information
    def print_cluster(self):
        print "-" * 80
        print "Name:\t\t%s"        % self.name
        print "Address:\t%s"       % self.network_address
	print "Type:\t\t%s"        % self.cloud_type
        print "VM Slots:\t%s"      % self.vm_slots
        print "CPU Cores:\t%s"     % self.cpu_cores
        print "Storage:\t%s"       % self.storageGB
        print "Memory:\t%s"        % string.join(self.memory, ", ")
        print "CPU Archs:\t%s"     % string.join(self.cpu_archs, ", ")
        print "Network Pools:\t%s" % string.join(self.network_pools, ", ")	
        print "-" * 80
    
    # Print a short form of cluster information
    def print_short(self):
        print "CLUSTER Name: %s, Address: %s, Type: %s, VM slots: %d, Mem: %s" \
	  % (self.name, self.network_address, self.cloud_type, self.vm_slots, \
	  string.join(self.memory, ", "))

    # Print the cluster 'vms' list (via VM print)
    def print_vms(self):
        if len(self.vms) == 0:
	    print "CLUSTER %s has no running VMs..." % (self.name)
	else:
	    print "CLUSTER %s running VMs:" % (self.name)
            for vm in self.vms:
	        vm.print_short("\t")
    
    # Finds a memory entry in the Cluster's 'memory' list which supports the
    # requested amount of memory for the VM. If multiple memory entries fit
    # the request, returns the first suitable entry.
    # Parameters: memory - the memory required for VM creation
    # Return: The index of the first fitting entry in the Cluster's 'memory'
    #         list.
    #         If no fitting memory entries are found, returns -1 (error!)
    def find_mementry(self, memory):
        for i in range(len(self.memory)):
	   if self.memory[i] >= memory:
	       return i
	
	# If no entries found, return error code. 
	return(-1)


    # Workspace manipulation methods
    #-!------------------------------------------------------------------------
    # NOTE: In implementing subclasses of Cluster, the following method prototypes
    #       should be used (standardize on these parameters)
    #-!------------------------------------------------------------------------

    # Note: vm_id is the identifier for a VM, used to query or change an already
    #       created VM. vm_id will be a different entity based on the subclass's
    #       cloud software. EG:
    #       - Nimbus vm_ids are epr files
    #       - OpenNebula (and Eucalyptus?) vm_ids are names/numbers
    # TODO: Explain all params
    
    def vm_create(self, vm_name, vm_networkassoc, vm_cpuarch, vm_imagelocation, \
      vm_mem):
        print 'This method should be defined by all subclasses of Cluster\n'
        assert 0, 'Must define workspace_create'

    def vm_destroy(self, vm):
        print 'This method should be defined by all subclasses of Cluster\n'
        assert 0, 'Must define workspace_destroy'
    
    def vm_poll(self, vm):
        print 'This method should be defined by all subclasses of Cluster\n'
        assert 0, 'Must define workspace_poll'
        
    ## More potential functions: vm_move, vm_pause, vm_resume, etc.



## Implements cloud management functionality with the Nimbus service as part of
## the Globus Toolkit.

class NimbusCluster(Cluster):

    ## NimbusCluster specific instance variables
   
    # NimbusCluster 'vms' list is composed of tuples: (vm_epr, vm_mem)

    # Global Nimbus command variables
    VM_DURATION = "1000"
    VM_TARGETSTATE = "Running"
    
    
    ## NimbusCluster specific instance methods
    
    # Overridden constructor
    def __init__(self, ):
        print "dbg - New NimbusCluster created"

    def vm_create(self, vm_name, vm_networkassoc, vm_cpuarch, vm_imagelocation,\
      vm_mem):
        
	print "dbg - Nimbus cloud create command"

	# Create a workspace metadata xml file from passed parameters
        vm_metadata = nimbus_xml.ws_metadata_factory(vm_name, vm_networkassoc, \
	  vm_cpuarch, vm_imagelocation)
	
	# Set a timestamp for VM creation
	now = datetime.datetime.now()
	
	# Create an EPR file name (unique with timestamp)
	vm_epr = "nimbusVM_" + now.isoformat() + ".epr"

        # Create the workspace command as a list (private method)
	ws_cmd = self.vmcreate_factory(vm_epr, vm_metadata, self.VM_DURATION, vm_mem, \
	  self.VM_TARGETSTATE)
	logging.debug("Nimbus: workspace create command prepared.")
	logging.debug("Command: " + string.join(ws_cmd, " "))

	# Execute a no-wait workspace command with the above cmd list.
	# Returns immediately to parent program. Subprocess continues to execute, writing to log.
	# stdin, stdout, and stderr set the filehandles for streams. PIPE opens a pipe to stream
	# (PIPE streams are accessed via popen_object.stdin/out/err)
	# Can also specify a filehandle or file object, or None (default).
	sp = Popen(ws_cmd, executable="workspace", shell=False, stdout=vm_log, stderr=vm_log)
	logging.debug("Nimbus: workspace create command executed.")

	# Find the memory entry in the Cluster 'memory' list which _create will be 
	# subtracted from
	vm_mementry = self.find_mementry(vm_mem)
	if (vm_mementry < 0):
	    # At this point, there should always be a valid mementry, as the ResourcePool
	    # get_resource methods have selected this cluster based on having an open 
	    # memory entry that fits VM requirements.
	    print "ERROR - vm_create - Cluster memory list has no sufficient memory " +\
	      "entries. FATAL. System exiting..."
	    sys.exit(1)
	print "dbg - vm_create - Memory entry found in given cluster: %d" % vm_mementry
	
	# Create a VM object to represent the newly created VM
	new_vm = VM(vm_name, vm_epr, self.network_address, self.cloud_type, \
	  vm_networkassoc, vm_cpuarch, vm_imagelocation, vm_mem, vm_mementry)
	
	# Add the new VM object to the cluster's vms list
	self.vms.append(new_vm)

	# TODO: Write a private 'checkout' method to do resource checkout?
	self.vm_slots -= 1
	self.memory[vm_mementry] -= vm_mem       
	
	logging.info("Nimbus: Workspace create command executed. VM created and stored, cluster updated.")

    
    def vm_destroy(self, vm):
        print 'dbg - Nimbus cloud destroy command'
        
        # TODO: Poll vm to check vm state. If Starting, return a wait message.
	#       Otherwise, destroy.

	# Create the workspace command with destroy option as a list (priv.)
	ws_cmd = self.vmdestroy_factory(vm.id)
	logging.debug("Nimbus: workspace destroy command prepared.")
	logging.debug("Command: " + string.join(ws_cmd, " "))

	# Execute the workspace command: no-wait, stdout to log.
	sp = Popen(ws_cmd, executable="workspace", shell=False, stdout=vm_log, stderr=vm_log)
	logging.debug("Nimbus: workspace destroy command executed.")

	# TODO: Check destroy return code. If successful, continue.
	#       Otherwise, set VM into error state (wait, and the polling)
	#       (thread will attempt a destroy later)

	# Return resources to cluster (currently only vm_slots and memory) and
	# remove VM epr from 'vms' list
	# TODO: Write a private 'return' method to handle resource return
	self.vm_slots += 1
	self.memory[vm.mementry] += vm.memory
	
	# Remove VM from the Cluster's 'vms' list
	self.vms.remove(vm)

	logging.info("Nimbus: Workspace destroy command executed. \
	  VM destroyed and removed, cluster updated.")


    def vm_poll(self, vm):
        print 'dbg - Nimbus cloud poll command'
	print 'dbg - should fork and execute (or possibly just execute) a workspace- \
          control command with the "rpquery" option'


    ## NimbusCluster private methods

    # The following _factory methods take the given parameters and return a list 
    # representing the corresponding workspace command.

    def vmcreate_factory(self, epr_file, metadata_file, duration, mem, \
      deploy_state):

        ws_list = ["workspace", 
           "-z", "none",
           "--poll-delay", "200",
           "--deploy",
           "--file", epr_file,
           "--metadata", metadata_file,
           "--trash-at-shutdown",
           "-s", "https://" + self.network_address  + ":8443/wsrf/services/WorkspaceFactoryService",
           "--deploy-duration", duration,    # minutes
           "--deploy-mem", str(mem),         # megabytes (convert from int)
           "--deploy-state", deploy_state,   # Running, Paused, etc.
           "--exit-state", "Running",        # Running, Paused, Propagated - hard set.
           # "--dryrun",                     
          ]

        # Return the workspace command list
	return ws_list

    def vmdestroy_factory(self, epr_file):
	ws_list = [ "workspace", "-e", epr_file, "--destroy"]
	return ws_list

    def vmpoll_factory(self, epr_file):
	ws_list = [ "workspace", "-e", epr_file, "--rpquery"]
	return ws_list

    
