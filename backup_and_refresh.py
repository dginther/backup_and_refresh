import sys
import os
import tarfile
import time
import socket
from netaddr import IPNetwork, IPAddress
import subprocess
import git
import pipes
import re
import pexpect



# Set this to your base path for client data
base_path = '/home/rs/Desktop/Clients/'

# Set this to your Tools folder
tools_path = '/home/rs/Desktop/Tools/'

# Set this to the CIDR range that your destination server resides on. This is hacky but we're not making grand pianos
#red_net = IPNetwork('192.168.20.0/24')
red_net = IPNetwork('10.30.10.0/24')

# Set this to your file destination URI
fileserver_uri = "user@host:/data/Clients/"

# Set this to the patch of the Nessus vmx file
nessus_vmx = '/var/lib/vmware/Shared VMs/TenableAppliance/TenableAppliance-VMware-4.2.0-standard.vmx'

# Set this to the patch of the Nessus vmx file
nexpose_vmx = '/var/lib/vmware/Shared VMs/NexposeVA/NexposeVA.vmx'

def info():
	# Warn user that this program will make modifications to their data
	print "This program will make modifications to the data on your drive. Specifically it will:\n- Revert the scanner VMs to a clean snapshot\n- Copy any data in " + base_path + " to a central server\n- Revert the /home partition to a clean btrfs snapshot\nIs this what you want to do?"

def dryrun_tar():
	# Let's do a dry run!
	date = time.strftime('%m-%d-%Y')
	
	# Is there data in the client data dir?
	if os.listdir(base_path) == []:
		# Nooooope. 
		print "No client data in "+ base_path
	else:
		# Client data exists! Tar it up, theoretically!
		for dirname, dirnames, filenames in os.walk(base_path, topdown=False):
				for subdirname in dirnames:
					print "Compressing: "+(os.path.join(dirname,subdirname))
					client = subdirname.replace(" ","_")
					client = client.lower()
  					print "Would have created file: " + str(os.path.join(dirname)) + client + "-" + date + ".tar.gz"

def on_red():
	
	# Kludgy way to get our current IP address without knowing the name of the interface
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.connect(("8.8.8.8", 80))
	my_ip = IPAddress(str(s.getsockname()[0]))

	if my_ip in red_net:
		return True
	else:
		return False


def tar_data():
	#
	# Data will be added to a client named tarfile with spaces replaced with underscores, and lower cased. 
	# Tar file format: <client_name>/<date>/<files>
	#

	date = time.strftime("%m-%d-%Y")
	
	# Is there data in the client data dir?
	if os.listdir(base_path) == []:
		print "No client data in "+ base_path
	else:
		# Client data exists! Tar it up!
		print "Tarring up customer data.\n"
		for dirname, dirnames, filenames in os.walk(base_path, topdown=False):
				for subdirname in dirnames:
					client = subdirname.replace(" ","_")
					client = client.lower()
					print "Compressing: "+os.path.join(dirname,subdirname) + " -> " + base_path + client + '-' + date + '.tar.gz'
					with tarfile.open(base_path + client + '-' + date + '.tar.gz', mode='w:gz') as archive:
						archive.add(os.path.join(dirname,subdirname), recursive=True, arcname=client + '/' + date)

					#upload file

def progress(locals):
	# extract percents
	print(int(re.search(br'(\d+)%$', locals['child'].after).group(1)))

def upload_file(file, server_uri):
	command = "scp %s %s" % tuple(map(pipes.quote, [file, server_uri]))
	pexpect.run(command, events={r'\d+%': progress})


def rollback_btrfs():
	# Roll back the btrfs partition.
	print "Rolling back btrfs snapshot of /home partition."
	rollback = raw_input('Continue? y/n: ')
	rollback = str(rollback.lower())
	if rollback == 'n':
		print "Exiting.\n"
		sys.exit()
	elif rollback == 'y':
		print "Rolling back btrfs partition.\n"
		# Do some fancy btrfs stuff here

def revert_vmware():
	# Revert the VMware appliances back to a prior snapshot
	print "Reverting VMWare appliances to snapshot."
	revert = raw_input('Continue? y/n: ')
	revert = str(revert.lower())
	if revert == 'n':
		print "Exiting.\n"
	elif revert == 'y':
		#
		# Do some tricky VMware vmrun stuff
		#

		print "Reverting VMware snapshots."
		nessus_snaps = subprocess.Popen(["vmrun", "-T", "ws", "listSnapshots", nessus_vmx], stdout=subprocess.PIPE).communicate()[0]
		nexpose_snaps = subprocess.Popen(["vmrun", "-T", "ws", "listSnapshots", nexpose_vmx], stdout=subprocess.PIPE).communicate()[0]
		if int(nessus_snaps[17]) == 0:
			print "No Nessus snapshots!"
		elif int(nessus_snaps[17]) >= 2:
			print "There is more than one snapshot. Please delete all unnecessary snapshots and rerun this script."
		else:
			print "Reverting Nessus snapshot."
			print nessus_snaps[19]
			#nessus_snap_status = subprocess.Popen(["vmrun", "-T", "ws", "revertToSnapshot", nessus_snaps[0], nessus_vmx], stdout=subprocess.PIPE).communicate()[0]
			#print str(nessus_snap_status)
		if nexpose_snaps == []:
			print "No Nexpose snapshots!"
		else:
			print "Reverting Nexpose snapshot."
			print nexpose_snaps
			#nessus_snap_status = subprocess.Popen(["vmrun", "-T ws revertToSnapshot", nexpose_snaps[0], nexpose_vmx], stdout=subprocess.PIPE).communicate()[0]
			#print str(nexpose_snap_status)

def is_git_directory(path):
	return subprocess.call(['git', '-C', path, 'status'], stderr=subprocess.STDOUT, stdout=open(os.devnull, 'w')) == 0

def update_tools():
	# update any tools which are git based 
	if os.listdir(tools_path) == []:
		print "No tools found.\n"
	else:
		for dirname, dirnames, filenames in os.walk(tools_path, topdown=False):
				for subdirname in dirnames:
					if is_git_directory(os.path.join(dirname,subdirname)):
						print "Updating: "+(os.path.join(dirname,subdirname))
						g = git.cmd.Git(os.path.join(dirname,subdirname))
						g.pull()

def main():
	
	# Print out a short description of what the tool does!
	info()

	# Get user's permission to continue
	yes_no = raw_input('Y/n/dry: ')
	yes_no = str(yes_no.lower())
	
	# User said no :(
	if yes_no == 'n':
		print "Quitting.\n"
	
	# Do a dry run
	elif yes_no == 'dry':
		print "Dry Run..."
		dryrun_tar()

	# DO IT TO IT
	elif yes_no == 'y':
		print "Proceeding.\n"
		
		# Check to see if we are connected to the red network defined above
		if on_red() == False:
			# Nooooooope. 
			print "Not on Red Network. Please make sure you are connected to the proper network.\n"
			sys.exit()
		# All is well, we are on red network.
		
		# Tar up the customer data	
		tar_data()

		# Roll back the btrfs partition snapshot
		rollback_btrfs()

		# Revert the VMware appliances
		revert_vmware()

		# Update tools
		update_tools()

		print "Done.\n"

	else:
		print "No decision?"



if __name__ == "__main__":
	main()



