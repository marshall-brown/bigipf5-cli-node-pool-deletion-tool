import ipaddress
import subprocess
import sys
import time
from datetime import datetime, timedelta
import icontrol.exceptions

server = ""
user = ""
password = ""

try:
    import f5.bigip
except ImportError:
    print("Missing required f5 SDk. 'ManagementRoot'")

try:
    from yaspin import yaspin
except ImportError:
    print("Missing required yaspin module. Will try to install now")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yaspin"])

try:
    from yaspin.spinners import Spinners
except ImportError:
    print("Missing required yaspin.spinners module. Will try to install now")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yaspin"])

sys.setrecursionlimit(
    10000)  # Allow python to recurse more than the default 999. There are over 4000 Pools we need to iterate through :(


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


try:
    mgmt = f5.bigip.ManagementRoot(server, user, password)
    ltm = mgmt.tm.ltm
except icontrol.exceptions.iControlUnexpectedHTTPError as e:
    sys.exit(bcolors.FAIL + "Cannot authenticate please check your credentials \n ------- \n Error Thrown: \n" + str(
        e) + bcolors.ENDC)
except ConnectionAbortedError as e:
    sys.exit(
        bcolors.FAIL + "Cannot authenticate please check your credentials. Connection Aborted with error: \n" + str(
            e) + bcolors.ENDC)
except ConnectionRefusedError as e:
    sys.exit(
        bcolors.FAIL + "Cannot authenticate please check your credentials. Connection refused with error: \n" + str(
            e) + bcolors.ENDC)
except ConnectionResetError as e:
    sys.exit(bcolors.FAIL + "Cannot authenticate please check your credentials. Connection reset with error: \n" + str(
        e) + bcolors.ENDC)
except ConnectionError as e:
    sys.exit(bcolors.FAIL + "General connection error with error: \n")

pool_members = []
pool_name = []
pools = []
now = datetime.now()  # current date and time

while True:
    question_1 = input(bcolors.HEADER + "Would you like to clean up empty pools? ([y]es/[n]o Enter=no): " + bcolors.ENDC).lower()
    answers = ["yes", "y", "no", "n"]
    if question_1 == "":
        question_1 = False
        break
    if question_1 not in answers:
        print("yes or no please")
        continue
    if question_1 in ["yes", "y"]:
        question_1 = True
        break
    else:
        question_1 = False
        break

if question_1:
    print(bcolors.WARNING + "We will be cleaning out the empty pools")
    print("This can take 5+ minutes please be patience")
    input("Press Enter to continue \n" + bcolors.ENDC)
else:
    print(bcolors.WARNING + "We will NOT be cleaning out the empty pools")
    print("-----" + bcolors.ENDC)

while True:
    ip = input(
        bcolors.HEADER + "What is the ipv4 address you are trying to cleanup? \n"+ bcolors.WARNING + "Enter nothing "
                                                                                                     "to skip cleanup "
                                                                                                     "\n \n" +
        bcolors.ENDC + bcolors.HEADER + "If multiple IP addresses please "
                         "list comma seperated \n Example: 172.16.16.16,172.16.16.17 \n ------- \n Enter IP[s] or "
                         "enter nothing to skip cleanup: " + bcolors.ENDC).split(',')
    if not all(ip):
        print(bcolors.WARNING + "\n No IPs given. Continuing... \n -------" + bcolors.ENDC)
        break
    else:
        try:
            for ipList in ip:
                ipaddress.ip_address(ipList)
            break
        except ValueError:
            print(
                bcolors.FAIL + "\n" + ipList + ": Is not a valid IPv4 IP address. Please Try again \n ------" + bcolors.ENDC)
            continue


def f5_nodes_search():
    print("Starting node search")
    global f5_nodes
    f5_nodes = mgmt.tm.ltm.nodes.get_collection()
    print("Finish node search")


def f5_pools_search():
    print("Starting pool search")
    global f5_pools
    f5_pools = mgmt.tm.ltm.pools.get_collection()
    print("Finish pool search")


def member_search():
    with yaspin(Spinners.clock, text="Searching for pool members please wait. Can take some time. 3 min+", side="right",
                color="green"):
        for pool in f5_pools:  # Lets get the pools and the nodes/members that are apart of the pools
            for pool_member in pool.members_s.get_collection():
                if pool_member.address in ip:
                    print("Pool member found with a name of " + pool_member.name)
                    print("\nPool name found with a name of " + pool.name + "\n")
                    pool_members.append(pool_member.name)
                    pool_name.append(pool.name)
                    pools.append(pool)


def deletenode():
    for node in f5_nodes:
        if node.address in ip:
            print(ip)
            print("Inside Deletenode func " + node.address)
            f = open("node_delete" + now.strftime("%Y-%m-%d-%H-%M"), "a")
            f.write(node.address)
            f.close()
            node.delete()
            print("Deleting Nodes")


def deletepool():
    member_search()
    for pool in f5_pools:
        if pool.name in pool_name:  # iterate through the pool list. If the pool
            print("Inside deletepool function")
            print(pool.name)
            print(pool_name)
            print(pool)
            f = open("pool_delete" + now.strftime("%Y-%m-%d-%H-%M"), "a")
            f.write(pool.name)
            print("Deleting the following pools " + pool.name)
            f.close()
            pool.delete()


def deleteemptypool():
    member_search()
    with yaspin(Spinners.clock, text="Deleting empty pools please wait. Can take some time. 5 min+", side="right",
                color="green"):
        for pool in f5_pools:
            if pool.members_s.items:
                continue
            else:
                print("\nDeleting Empty Pool \n" + pool.name)
                f = open("empty_pools" + now.strftime("%Y-%m-%d"), "a")
                print("Writing empty pool to file\n")
                f.write(pool.name + "\n")
                f.close()
                try:
                    pool.delete()
                except Exception as e:
                    if "is referenced by one or more rules" in e.response.text:
                        print(bcolors.FAIL +
                              "Cannot delete the following pool. \n ------- \n" + pool.name + "\n ------- \n This pool has a "
                                                                                              "irule attached to it. \n "
                                                                                              "Please talk to Daniel for "
                                                                                              "remedy \n ------- \n "
                                                                                              "Continuing search... \n" +
                              bcolors.ENDC)
                    else:
                        print(
                            bcolors.FAIL + "A unhandled exception occurred deleting the following empty pool \n "
                                           "------- \n" + pool.name + "\n------\n Please talk to Daniel for remedy \n "
                                                                      "------- \n Continuing search... \n" +
                            bcolors.ENDC)

    file = open("empty_pools" + now.strftime("%Y-%m-%d"), "r")
    counter = 0

    # Reading from file
    content = file.read()
    co_list = content.split("\n")

    for i in co_list:
        if i:
            counter += 1

    print("This is the number of lines in the file")
    print(counter)


def main():
    start = time.time()
    if question_1:
        f5_pools_search()
        deleteemptypool()

    if all(ip):
        f5_nodes_search()
        f5_pools_search()
        deletepool()
        deletenode()

    end = time.time()
    print(bcolors.OKBLUE + "Script runtime: " + str(timedelta(seconds=int(end) - int(start))) + bcolors.ENDC)
    print("Meow")


if __name__ == '__main__':
    main()
