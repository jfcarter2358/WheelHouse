# Wheel House
---
The customer-focused evolution of Helm

## About
**Wheel House** is a Kubernetes (k8s) package manager designed to enable organizations to quickly and easliy get their software deployed into a k8s environment without the hassle of making a user download and run external scripts in order to configure their templates.  **Wheel House** works off of **Compass** packages which contain everything necessary to generate the k8s manifest files as well as an interaction declaration to get the the necessary configuration from the user.

## Usage
To list available **Wheel House** compass packages, run 
```
python wheel_house/wheel_house.py search <name to search for>
```

To see available versions for a given package, run
```
python wheel_house/wheel_house.py list <name to list versions for>
```