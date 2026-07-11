# 交给 Codex 的首次执行指令

请先完整阅读：

```text
sgcf_nrmp_project/docs/codex/SGCF_NRMP_Codex_Execution_Plan_V2.md
```

然后严格执行其中的 **阶段 01：仓库审计、基线确认与独立工程骨架**。

执行要求：

1. 只执行阶段 01，不要开始阶段 02 或任何后续功能。
2. 不得修改 `neupan/`、`neupan_ros/`、`neupan_ros2/`、`example/`、`docker/`。
3. 不得自动执行 `git restore`、`git reset --hard`、`git clean -fd`、commit 或 push。
4. 官方只读算法基线固定为提交 `579e7af`。当前工作树中的 DeepSeek/Color-DUNE、Semantic DUNE、`class_embed`、`point_class` 等修改均视为已知错误，不恢复、不兼容、不作为实验基线；审计时记录差异，但不得修改受保护目录。
5. 遇到网络失败、sudo、软件安装、模型下载、数据下载、凭据、GUI、硬件或版本冲突时立即停止并提问。
6. 阶段完成后必须生成：

```text
sgcf_nrmp_project/artifacts/stages/stage_01_*/stage_report.md
commands.log
tests.log
environment.txt
files_changed.txt
upstream_check.txt
outputs/
```

7. 至少给出一个我能直接看到的结果：仓库审计报告、环境报告、项目目录树和导入测试结果。
8. 完成后停止，并明确说明没有开始阶段 02。
