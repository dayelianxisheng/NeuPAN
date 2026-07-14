# Known limitations

- The rebuilt image is functionally equivalent, not byte-identical, to the unavailable historical image.
- The formal robot asset still contains no visibility isolation; this stage validated only a `/tmp` copy.
- Only `empty_world` was run. External-obstacle preservation remains for the separately authorized formal-fix regression.
- The existing historical container is not a reproducible baseline and was not used for runtime diagnosis.
