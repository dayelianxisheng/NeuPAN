# Installation Validation

Validation must use the derived image's full immutable ID and no GPU exposure.

System environment:

```bash
/usr/bin/python3 -c 'import rclpy,numpy,scipy; print(numpy.__version__, scipy.__version__)'
```

Planner environment:

```bash
/opt/sgcf_planner_venv/bin/python -c \
  'import rclpy,numpy,scipy,torch,cvxpy,osqp; print(torch.__version__, torch.cuda.is_available())'
```

Expected distinction:

```text
Torch build: CUDA-capable cu128
GPU exposed: false
Planner execution: CPU only
```
