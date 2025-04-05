#!/bin/bash
# Start Fail2Ban
/usr/bin/fail2ban-client start

# Start Nginx in the foreground
/usr/sbin/nginx -g 'daemon off;'