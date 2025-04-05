#!/bin/sh
# Start Nginx in the foreground
/usr/sbin/nginx -g 'daemon off;'

# Start Fail2Ban
sleep 10

# Start Fail2Ban
if [ ! -S /var/run/fail2ban/fail2ban.sock ]; then
    rm /var/run/fail2ban/fail2ban.sock
fi

/usr/bin/fail2ban-client start
