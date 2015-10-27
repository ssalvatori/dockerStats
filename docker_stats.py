#! /usr/bin/env python

import argparse
import docker
import json
import logging
import socket
import sys

class DockerStats():

    def __init__(self, url, cpuLimits, ramLimits, iodiskLimits, ionetLimits):
        self.url = url
        self.cpuLimits = cpuLimits
        self.ramLimits = ramLimits
        self.iodiskLimits = iodiskLimits
        self.ionetLimits = ionetLimits
        self.statusDict = {}
        self.conn = docker.Client(base_url=self.url, timeout=20)
        self.messages = []
        self.hostname = socket.gethostname()

        try :
            self.containers = self.conn.containers()
        except :
            print("WARNING: There is not containers available to monitor or host not reachable")
            sys.exit(ContainerStatus.WARNING)
	
    def stats(self):
        logging.info("action=num_containers total=" + str(len(self.containers)))

        for container in self.containers:
            container_id = str(container["Id"])
            container_img = str(container["Image"])
            container_name = container["Names"][0].split('/')[1]
            docker_image = self.conn.images(container_img.split(':')[0])
            docker_image_tags = ""
            if isinstance(docker_image, list) :
                if "RepoTags" in docker_image[0] :
                    docker_image_tags = ";".join(docker_image[0]["RepoTags"])

            stats = self.conn.stats(container_id)
            curStat = stats.next()
            summaryStr = self._readStat(curStat,container_id, container_img, docker_image_tags, container_name)
            self._monitorContainerStats(container_id)
            logging.info(summaryStr)
                
        sys.exit(self.responseExitCode())

    def getStatusExit(self):
        badStatusList =  [ContainerStatus.WARNING, ContainerStatus.CRITICAL]
        statusToReturn = ContainerStatus.OK
  
        for contId, contStatus in self.statusDict.items():
            for status in contStatus.resourceDict.itervalues():
                if status in badStatusList:
                    if status == ContainerStatus.CRITICAL:
                        return ContainerStatus.CRITICAL
                    else:
                        statusToReturn = status

        return statusToReturn
			  
    def responseExitCode(self):
        if len(self.messages) > 0:
            print('::'.join(self.messages))
        else:
            print("OK: Everything is OK")

        return self.getStatusExit()
			  
			
    def _monitorContainerStats(self, container_id):
        self.statusDict[container_id] = ContainerStatus(container_id)
        
        #check ramLimits
        ramUsage = self._getPercentage(self.summaryData["memory_usage"], self.summaryData["memory_limit"])
        self.statusDict[container_id].resourceDict["ramStatus"] = self._validateLimits(container_id, ramUsage, self.ramLimits, "RAM")
                
        #check cpuLimits
        cpuUsage = self._getPercentage(self.summaryData["cpu_usage"], self.summaryData["cpu_total_system"])
        self.statusDict[container_id].resourceDict["cpuStatus"] = self._validateLimits(container_id, cpuUsage, self.cpuLimits, "CPU")
        
        
        # UNCOMMMENT FOR IO STATS
        
        #check iodiskLimits
        #iodiskUsage = 74113024 # TODO HARDCODED self.summaryData["blkio_io_service_bytes"]["Total"]
        #self.statusDict[container_id].resourceDict["iodiskStatus"] = self._validateLimits(container_id, iodiskUsage, self.iodiskLimits, "IO_DISK")
        
        #check ionetLimits
        #ionetUsage = int(self.summaryData["network_rx_bytes"]) + int(self.summaryData["network_tx_bytes"])
        #self.statusDict[container_id].resourceDict["ionetStatus"] = self._validateLimits(container_id, ionetUsage, self.ionetLimits, "IO_NETWORK")
			
			
    def _validateLimits(self, container_id, usage, limits, resource):
        status = ContainerStatus.UNKNOWN
        if usage < limits.warningLim:
            status = ContainerStatus.OK # OK
        elif usage >= limits.warningLim and usage < limits.criticalLim:
            status = ContainerStatus.WARNING # Warning
            self.messages.append("WARNING " + resource + ": The Container " + container_id[:8] + " has % level of " + resource + ": " + str(usage)[:6])
        elif usage >= limits.criticalLim:
            status = ContainerStatus.CRITICAL # Critical
            self.messages.append("CRITICAL " + resource + ": The Container " + container_id[:8] + " has % level of " + resource + ": " + str(usage)[:6])

        return status
				
		      
    def _getPercentage(self, fraction, whole):
        return (float(fraction)/float(whole))*100

    def _readStat(self,stats,container_id, container_img, docker_img_tags, container_name):
        statsObj = json.loads(stats)

        self.summaryData = dict(
            container_id=container_id,
            container_img=container_img,
            container_name=container_name,
            docker_image_tags=docker_img_tags,
            hostname=self.hostname,
            memory_usage=json.dumps(statsObj["memory_stats"]['usage']),
            memory_limit=json.dumps(statsObj["memory_stats"]['limit']),
            cpu_usage=json.dumps(statsObj["cpu_stats"]["cpu_usage"]["total_usage"]),
            cpu_total_system=json.dumps(statsObj["cpu_stats"]["system_cpu_usage"]),
            network_rx_bytes=json.dumps(statsObj["network"]["rx_bytes"]),
            network_tx_bytes=json.dumps(statsObj["network"]["tx_bytes"]),
            network_rx_dropped=json.dumps(statsObj["network"]["rx_dropped"]),
            network_tx_dropped=json.dumps(statsObj["network"]["tx_dropped"]),
            network_rx_errors=json.dumps(statsObj["network"]["rx_errors"]),
            network_tx_errors=json.dumps(statsObj["network"]["tx_errors"]),
            network_rx_packet=json.dumps(statsObj["network"]["rx_packets"]),
            network_tx_packet=json.dumps(statsObj["network"]["tx_packets"]),
            blkio_io_service_bytes=json.dumps(statsObj["blkio_stats"]["io_service_bytes_recursive"]),
            blkio_io_serviced=json.dumps(statsObj["blkio_stats"]["io_serviced_recursive"]),
            blkio_io_queue=json.dumps(statsObj["blkio_stats"]["io_queue_recursive"])
        )

        summaryStr = "action=stats "
        for key,value in self.summaryData.items():
            summaryStr += " "+key+"="+value

        return summaryStr
		      
class Limits():
    def __init__(self, warningLim, criticalLim):
        self.warningLim = warningLim
        self.criticalLim = criticalLim

class ContainerStatus():
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3
  
    def __init__(self, container_id):
        self.container_id = container_id
        
        self.resourceDict = dict(
            cpuStatus = self.UNKNOWN,
            ramStatus = self.UNKNOWN,
            iodiskStatus = self.UNKNOWN,
            ionetStatus = self.UNKNOWN
        )

def main():
    argp = argparse.ArgumentParser()
    argp.add_argument('-u', '--url', metavar='URL',
                                      help='URL string for Docker service.',
                                      default='unix://var/run/docker.sock')
    
    argp.add_argument('-w_cpu', metavar='CPU Warning Limit', type=float, help='Warning percentage limit for CPU usage')
    argp.add_argument('-c_cpu', metavar='CPU Critical Limit', type=float, help='Critical percentage limit for CPU usage')
    argp.add_argument('-w_ram', metavar='RAM Warning Limit', type=float, help='Warning percentage limit for RAM usage')
    argp.add_argument('-c_ram', metavar='RAM Critical Limit', type=float, help='Critical percentage limit for RAM usage')
    argp.add_argument('-w_iodisk', metavar='IO Disk Warning Limit', type=float, help='Warning percentage limit for Hard Disk IO usage')
    argp.add_argument('-c_iodisk', metavar='IO Disk Critical Limit', type=float, help='Critical percentage limit for Hard Disk IO usage')
    argp.add_argument('-w_ionet', metavar='IO Network Warning Limit', type=float, help='Warning percentage limit for Network IO usage')
    argp.add_argument('-c_ionet', metavar='IO Network Critical Limit', type=float, help='Critical percentage limit for Network IO usage')
    

    args = argp.parse_args()
    
    cpuLimits = Limits(args.w_cpu, args.c_cpu)
    ramLimits = Limits(args.w_ram, args.c_ram)
    iodiskLimits = Limits(args.w_iodisk, args.c_iodisk)
    ionetLimits = Limits(args.w_ionet, args.c_ionet)

    logging.basicConfig(level=logging.INFO, filename="/var/log/docker-stats.log", format='%(asctime)s %(message)s')
    docker_stats = DockerStats(args.url, cpuLimits, ramLimits, iodiskLimits, ionetLimits)
    docker_stats.stats()



if __name__ == '__main__':
    main()
