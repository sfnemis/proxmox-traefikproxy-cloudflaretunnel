#!/usr/bin/env python3
import requests
import yaml
import re
import os
import time
import json
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/var/log/traefik-dns.log'
)
logger = logging.getLogger('traefik-dns')

# Configuration - REPLACE THESE VALUES
CF_API_TOKEN = "YOUR_CLOUDFLARE_API_TOKEN"
ZONE_ID = "YOUR_CLOUDFLARE_ZONE_ID"
BASE_DOMAIN = "example.com"  # Your domain
TRAEFIK_CONFIG_DIR = "/etc/traefik/dynamic"
TRAEFIK_API_URL = "http://localhost:8080/api"

def get_hosts_from_traefik_api():
    """Get hosts from Traefik API"""
    try:
        response = requests.get(f"{TRAEFIK_API_URL}/http/routers")
        if response.status_code != 200:
            logger.error(f"Error accessing Traefik API: {response.status_code}")
            return []
        
        hosts = []
        for router in response.json():
            rule = router.get("rule", "")
            # Look for Host rules - can be in different formats like Host(`domain`) or Host(`domain`,`domain2`)
            host_matches = re.findall(r"Host\(`([^`]+)`\)", rule)
            hosts.extend(host_matches)
        
        return hosts
    except Exception as e:
        logger.error(f"Error accessing Traefik API: {e}")
        return []

def get_hosts_from_config_files():
    """Parse Traefik config files to extract hostnames"""
    hosts = []
    
    # Walk through all .yml files in the config directory
    for path in Path(TRAEFIK_CONFIG_DIR).rglob("*.yml"):
        try:
            with open(path, 'r') as file:
                config = yaml.safe_load(file)
                
                if not config or "http" not in config:
                    continue
                    
                if "routers" in config["http"]:
                    for router_name, router in config["http"]["routers"].items():
                        if "rule" in router:
                            rule = router["rule"]
                            host_matches = re.findall(r"Host\(`([^`]+)`\)", rule)
                            hosts.extend(host_matches)
        except Exception as e:
            logger.error(f"Error parsing {path}: {e}")
    
    return hosts

def get_existing_dns_records():
    """Get existing DNS records from Cloudflare"""
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records?per_page=100",
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"Error fetching DNS records: {response.status_code}, {response.text}")
            return []
            
        records = []
        for record in response.json()["result"]:
            records.append(record["name"])
        
        return records
    except Exception as e:
        logger.error(f"Error fetching DNS records: {e}")
        return []

def create_dns_record(hostname):
    """Create a new CNAME record in Cloudflare"""
    # Extract subdomain part
    if hostname.endswith(BASE_DOMAIN):
        subdomain = hostname[:-len(BASE_DOMAIN)-1]  # remove domain and dot
    else:
        subdomain = hostname
        
    # Don't create record for the base domain
    if subdomain == "":
        return
        
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "type": "CNAME",
        "name": subdomain,
        "content": BASE_DOMAIN,
        "ttl": 1,
        "proxied": True
    }
    
    try:
        response = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully created DNS record for {hostname}")
        else:
            logger.error(f"Error creating DNS record for {hostname}: {response.text}")
    except Exception as e:
        logger.error(f"Error creating DNS record for {hostname}: {e}")

def main():
    # Get all hosts from Traefik
    hosts_from_api = get_hosts_from_traefik_api()
    hosts_from_config = get_hosts_from_config_files()
    
    all_hosts = list(set(hosts_from_api + hosts_from_config))
    logger.info(f"Found {len(all_hosts)} hosts in Traefik configuration")
    
    # Filter out hosts that don't match our domain
    domain_hosts = [host for host in all_hosts if BASE_DOMAIN in host]
    logger.info(f"Found {len(domain_hosts)} hosts matching domain {BASE_DOMAIN}")
    
    # Get existing DNS records
    existing_records = get_existing_dns_records()
    logger.info(f"Found {len(existing_records)} existing DNS records in Cloudflare")
    
    # Create records for new hosts
    for host in domain_hosts:
        if host not in existing_records:
            logger.info(f"Creating DNS record for {host}")
            create_dns_record(host)
            # Avoid rate limits
            time.sleep(1)
        else:
            logger.debug(f"DNS record for {host} already exists")

if __name__ == "__main__":
    logger.info("Starting Traefik DNS automation run")
    main()
    logger.info("Completed Traefik DNS automation run")
