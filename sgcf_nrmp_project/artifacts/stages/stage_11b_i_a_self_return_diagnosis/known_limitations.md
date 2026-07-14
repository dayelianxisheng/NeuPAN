# Known limitations

- The result proves a visibility-only fix is feasible in a temporary copy; formal Gazebo assets remain unchanged.
- The probe used `empty_world` only and does not validate visibility behavior against external obstacles.
- The scan plane remains geometrically coplanar with robot visual surfaces until a formal visibility fix is authorized.
- Image bytes are not identical to the historical build, although locked Gazebo / SDFormat / rendering functionality is equivalent.
- The locally tagged image was rebuilt after the running container; the audited runtime identity is the container image ID recorded in the environment audit.
