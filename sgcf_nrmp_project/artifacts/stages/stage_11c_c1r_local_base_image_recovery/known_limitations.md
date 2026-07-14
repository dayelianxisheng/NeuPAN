# Known limitations

The default BuildKit probe canonicalized the local alias as a docker.io name and fetched the Dockerfile frontend, violating the strict zero-network probe contract.
