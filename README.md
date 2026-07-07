# DE CI/CD Lambda Demo

一个很小的 Data Engineering CI/CD 示例：

- Lambda 接收 S3 CSV 上传事件
- 读取 raw CSV
- 做字段标准化和简单数据清洗
- 写出 curated JSONL 到另一个 S3 prefix
- GitHub Actions 在 PR merge 到 `main` 后自动部署代码到 AWS Lambda

## 项目结构

```text
.
├── .github/workflows/deploy-lambda.yml
├── lambda/src/lambda_function.py
├── tests/test_lambda_function.py
├── requirements-dev.txt
└── README.md
```

## Lambda 环境变量

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `OUTPUT_BUCKET` | `my-curated-bucket` | 输出 JSONL 的 bucket；不设置时默认写回输入 bucket |
| `OUTPUT_PREFIX` | `curated/events` | 输出 prefix |

## 本地测试

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest
```

## GitHub Actions 部署配置

在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 配置：

| Secret / Variable | 示例 |
| --- | --- |
| `AWS_ROLE_TO_ASSUME` | `arn:aws:iam::123456789012:role/github-actions-lambda-deploy` |
| `AWS_REGION` | `us-east-1` |
| `LAMBDA_FUNCTION_NAME` | `de-cicd-demo` |

workflow 使用 GitHub OIDC 登录 AWS，不需要长期 AWS access key。PR merge 后会产生一次 push 到 `main`，因此 workflow 监听 `main` 分支的 push 来做 CD。

## AWS 侧最小准备

1. 创建 Lambda function，runtime 选择 Python 3.12，handler 设置为 `lambda_function.handler`。
2. 给 Lambda execution role 加上读取 raw S3 bucket、写入 curated S3 bucket 的权限。
3. 给 GitHub Actions OIDC role 加上 `lambda:UpdateFunctionCode` 权限。
4. 配置 S3 event notification，让 raw bucket 的 CSV 上传事件触发 Lambda。

