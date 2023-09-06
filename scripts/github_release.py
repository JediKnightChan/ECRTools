# This script will require a github personnal access token
# With repo permissions inside a github_token.txt file to function properly

from github import Github
from github import Auth
from github import GitRelease

# Method to create a github release on a specific repository
# param repository_full_name : The full name of the github repository for which to create the release (USER/REPOSITORY_NAME)
# param release_tag : The tag of the release to create, has to be different from the other releases' tags
# param release_name : The name of the release to create
# param release_message : The message for the release to create
# Returns a GitRelease.GitRelease representation of a github release with only the source files as assets
def create_github_release(repository_full_name, release_tag, release_name, release_message):
    # Get github personnal access token to interact with the API
    with open("github_token.txt") as infile:
        token = infile.read()

    # Create main PyGithub class
    auth = Auth.Token(token)
    g = Github(auth=auth)

    # Get repository
    repo = g.get_repo(repository_full_name)
    # Create release
    release = repo.create_git_release(release_tag, release_name, release_message)
    return release

# Method to add assets to an existing github release
# param github_release : A GitRelease.GitRelease representation of an existing github release
# param assets_paths : The paths to the assets to add to the github release
def upload_assets_to_github_release(github_release, assets_paths):
    for path in assets_paths:
        github_release.upload_asset(path)
