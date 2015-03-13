#! /usr/bin/env python

import argparse
import docker
import json
import logger

class DockerStats():

		def __init__(self, url):

			self.url = url
			self.conn = docker.Client(base_url=self.url, timeout=20)
	
		def stats(self):
			'''

			'''
			
			self.containers = self.conn.containers()

			for container in self.containers:

				print container

				#container_name = container["Names"][0].replace('/','')
				container_id = str(container["Id"])
				container_img = str(container["Image"])

				stats = self.conn.stats(container_id)

				for statStr in stats:
					print self._readStat(statStr,container_id, container_img)
					break


		def _readStat(self,stats,container_id, container_img):
			'''
			'''

			statsObj = json.loads(stats)

			summaryData = dict(
				container_id=container_id,
				container_img=container_img,
				memory_usage=str(statsObj["memory_stats"]['usage']),
				memory_limit=str(statsObj["memory_stats"]['limit']),
				cpu_usage=str(statsObj["cpu_stats"]["cpu_usage"]["total_usage"]),
				cpu_total_system=str(statsObj["cpu_stats"]["cpu_usage"]["total_usage"])
			)

			summaryStr = ""
			for key,value in summaryData.items():
				summaryStr += " "+key+"="+value

			return summaryStr

def main():

	argp = argparse.ArgumentParser()
	argp.add_argument('-u', '--url', metavar='URL',
					  help='URL string for Docker service.',
					  default='unix://var/run/docker.sock'),

	args = argp.parse_args()

	docker_stats = DockerStats(args.url)
	docker_stats.stats()



if __name__ == '__main__':
	main()