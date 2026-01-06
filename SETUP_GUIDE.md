# Project Thunder Setup Guide

이 문서는 Project Thunder v3.0의 초기 설정을 위한 가이드입니다.

## 1. 프로젝트 구조
```
pdf-lab/
├── web/            # Next.js Frontend (Firebase App Hosting)
├── backend/        # Python Backend (Cloud Run Jobs)
│   ├── src/        # Phase 1~4 Source Code
│   ├── Dockerfile
│   └── requirements.txt
├── infra/          # GCP Terraform code
└── ...문서들
```

## 2. 초기 설정 (Step-by-Step)

### A. Frontend (Web) 설정
`web` 디렉토리로 이동하여 의존성을 설치합니다.
```bash
cd web
npm install
# 개발 서버 실행 테스트
npm run dev
```
> **참고**: `firebase.json`이나 `apphosting.yaml`은 이미 생성되어 있습니다. Firebase Console에서 App Hosting을 연결할 때 이 레포지토리를 선택하면 자동으로 감지합니다.

### B. Backend 설정
Backend는 Docker 기반으로 동작하지만, 로컬 개발을 위해 가상환경을 권장합니다.
```bash
cd backend
python -m venv venv
# Windows
.\venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### C. Infrastructure (GCP)
Terraform을 사용하여 GCP 리소스를 프로비저닝합니다.
1. `infra` 디렉토리로 이동: `cd infra`
2. `terraform.tfvars` 파일 생성 (보안상 gitignore 처리 필요):
    ```hcl
    project_id = "YOUR_PROJECT_ID"
    region     = "asia-northeast3" # 서울 리전
    ```
3. 적용:
    ```bash
    terraform init
    terraform plan
    terraform apply
    ```

## 3. 배포 파이프라인
- **Frontend**: GitHub Main 브랜치에 푸시하면 Firebase App Hosting이 자동으로 빌드 및 배포합니다.
- **Backend**: `backend/` 변경 시 `gcloud builds submit` 또는 Cloud Build 트리거를 통해 Artifact Registry로 이미지를 푸시하고, Cloud Run Jobs를 업데이트합니다.

## 4. 로컬 테스트
- `backend/src/main.py`를 통해 각 페이즈를 로컬에서 테스트할 수 있습니다.
  ```bash
  # 예: Phase 1 실행 (테스트용)
  python -m src.main --phase 1 --job-payload '{"source_id": "test"}'
  ```
