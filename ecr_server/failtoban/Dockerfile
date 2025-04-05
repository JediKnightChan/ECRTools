# Use a base image that has fail2ban installed (such as an Alpine image)
FROM alpine:latest

# Install Fail2Ban and other required dependencies
RUN apk update && apk add --no-cache \
    fail2ban \
    iptables \
    bash

# Copy your jail.conf to configure Fail2Ban
COPY nginx/fail2ban/jail.conf /etc/fail2ban/jail.conf
COPY nginx/fail2ban/filter.d/ /etc/fail2ban/filter.d/
RUN rm -rf /etc/fail2ban/jail.d/

# Command to start Fail2Ban
ENTRYPOINT ["/usr/bin/fail2ban-client", "start"]