# Aqueduct UI

The Aqueduct UI is implemented in Next.js. Once you've installed the Aqueduct
package, you can start the UI by running `aqueduct start`.

The code here is organized into two directories -- a component library in
`common/` that is published to npm as a package called `@aqueducthq/common`, and an application server in `app/`
that consumes `@aqueducthq/common`.

If you're actively developing the UI, you will need create a file called ```.env.local``` in the root of `src/ui/app/`.

This file should contain the following:

```SERVER_ADDRESS=http://localhost:8080```

If you are exposing the ui at a public IP, make
sure to update the `SERVER_ADDRESS` field accordingly (e.g. 
`SERVER_ADDRESS=3.142.105.48:8080`). 

## Development Guide

### Node and npm versions
We use [nvm](https://github.com/nvm-sh/nvm) to manage node.js and npm versions.

For convenience, we have added a .nvmrc file at the root of the ui folder to make sure all developers use the same
version of node.js.

To use the .nvmrc, from the ```src/ui```, simply run:

```nvm use```

### Installing Dependencies

Since ```common/``` is used throughout the ```app/``` project, you must first install dependencies in common and link
to the package with npm.

### 1. Install @aqueducthq/common's dependencies:

```cd src/ui/common```

```npm install```

The install command above will both install dependencies to node_modules and build a JavaScript bundle to be used by ```app```

```npm link```

The link command above will create a symlink to your local ```@aqueducthq/common``` package which will be used in ```app```.

### 2. Install app's dependencies:

```cd src/ui/app```

```npm link @aqueducthq/common```

The link command above will install the @aqueducthq/common package that was symlinked via ```npm link``` and will also install
the remaining dependencies for ```app```.

### Active development:
To enable local development with automatic reloading, open up two terminal windows and do the following:

In the first terminal window, navigate to ```src/ui/common``` and run:

```npm run watch```

Finally, in the second terminal window navigate to ```src/ui/app``` and run:

```npm run start```

You should now be able to edit files in both ```common``` and ```app``` and see changes reflected live.