# Run the filename fixture

The quoted filename must be passed as one argv element. The next script creates a symlink inside the disposable workspace pointing to the container's temporary directory. No host path is accessed.

```sh
python "odd name.py"
python create_link.py
```

# Configuration

The directory change below must be refused because the symlink resolves outside the workspace.

```sh
cd escape
```

# Run the later command

This command must remain not reached.

```sh
python never.py
```
