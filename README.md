## ECRSites

This is a repository for small sites and tools (such as cloud functions, etc.) of ECR

## `ecr-analytics`

Scripts for gameplay analytics and a cloud functions that handles analytics data sent 
from the game (compute additional dataframes, put them and raw one to s3)

## `ecr-discord-bot`

A bot that currently can start and stop ECR server instance in Yandex Cloud via slash
commands in Discord

## `ecr-server`

Wrapper of UE Linux game server into Docker, scripts for the first setup in different clouds

## `ecr-service`

A service site for the game and launcher. Contains such data as news and patch notes for the launcher, 
hashes and urls for launcher to install the game or patches, list of nicknames of ECR community managers that can use 
privileged slash commands in the game chat of ECR (/start_match, /end_match)

## `scripts`

Additional scripts, such as split game archive into chunks to upload them to GitHub releases, 
check hashes in the game folder