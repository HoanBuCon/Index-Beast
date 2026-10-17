# Quy ước Git của nhóm 4 Hollows

Áp dụng cho dự án **IndexBeast**, bao gồm mã nguồn, cấu hình và tài liệu. Mọi thay đổi phải đi qua nhánh riêng và Pull Request (PR). Không commit hoặc push trực tiếp lên `main` / `master` hoặc `develop`.

## 1. Vai trò và vòng đời các nhánh

| Nhánh | Mục đích | Tách từ | Đích PR |
|---|---|---|---|
| `main` / `master` | Mã nguồn ổn định trên Production; repo này dùng `main` | Nhánh gốc | Chỉ nhận từ `release/*` hoặc `hotfix/*` |
| `develop` | Tích hợp tính năng hoàn thành, dùng cho Staging/QC | Thiết lập ban đầu từ `main` | Nhận feature và các PR đồng bộ release/hotfix |
| `feature/<mã-tác-vụ>-<tên-ngắn-gọn>` | Phát triển một tính năng hoặc thay đổi riêng, kể cả docs | `develop` | `develop` |
| `release/<phiên-bản>` | QA cuối đợt phát hành, chỉ sửa lỗi nhỏ phục vụ release | `develop` | `main` và `develop` |
| `hotfix/<mã-tác-vụ>-<tên-ngắn-gọn>` | Sửa lỗi khẩn cấp trên Production | `main` | `main` và `develop` |

Tên nhánh dùng chữ không dấu, số và dấu gạch nối. Ví dụ: `feature/task-1-rag-baseline`, `feature/docs-01-base-game-scope`, `release/v1.0.0`, `hotfix/bug-12-chat-timeout`. Không dùng các tiền tố `feat/`, `fix/`, `docs/`, `chore/` thay cho các loại nhánh trên; những tên này có thể là loại commit.

## 2. Quy trình cho một tác vụ

1. Đồng bộ remote và tạo feature từ `origin/develop` mới nhất.
2. Thực hiện thay đổi, kiểm tra và commit theo Conventional Commits.
3. Fetch rồi rebase nhánh cá nhân lên `origin/develop`; giải quyết conflict, kiểm tra lại.
4. Push nhánh feature và mở PR có **base là `develop`**.
5. Gắn mã/link tác vụ, mô tả thay đổi, cách kiểm tra và hạn chế còn lại. Yêu cầu Mentor review; chỉ merge sau khi Mentor approve, CI bắt buộc đạt và mọi conflict đã được giải quyết.
6. Sau merge, cập nhật trạng thái tác vụ. Chỉ xóa nhánh khi đã tích hợp xong và không còn người phụ thuộc.

Ví dụ thực hiện trên máy cá nhân:

```bash
git fetch origin
git switch -c feature/task-1-rag-baseline origin/develop
# Sửa file và chạy các kiểm tra phù hợp.
git add <cac-file-cua-tac-vu>
git commit -m "feat(rag): implement retrieval baseline"
git fetch origin
git rebase origin/develop
git push -u origin feature/task-1-rag-baseline
# Tạo PR: feature/task-1-rag-baseline -> develop; yêu cầu Mentor review.
```

Nếu rebase gặp conflict: sửa từng file, `git add <file>` rồi `git rebase --continue`; dùng `git rebase --abort` để hủy lần rebase nếu cần. Nếu nhánh cá nhân đã push trước khi rebase, dùng `git push --force-with-lease` sau khi kiểm tra; không dùng `--force`. Không tự rebase/ghi đè lịch sử nhánh chung mà chưa thống nhất với các thành viên đang dùng nhánh đó.

Không tạo commit "Dev Start" trực tiếp trên `develop`. Các commit trong ví dụ minh họa vòng đời đều phải tuân theo quy trình PR này.

## 3. Nhiều thành viên làm chung một tính năng

Với tính năng A, tạo nhánh chung `feature/A` từ `develop`, sau đó tạo nhánh cá nhân `feature/A.1`, `feature/A.2`, … từ `feature/A`. A phải được thay bằng mã tác vụ và tên ngắn gọn, ví dụ:

```text
develop
  -> feature/task-1-rag
       -> feature/task-1-rag.1 -> PR -> feature/task-1-rag
       -> feature/task-1-rag.2 -> PR -> feature/task-1-rag
     feature/task-1-rag       -> PR -> develop
```

Mỗi thành viên xử lý conflict bằng rebase nhánh cá nhân lên nhánh chung, chạy kiểm tra, rồi mở PR về nhánh chung. Yêu cầu Mentor review trước khi merge các PR. Khi toàn bộ tính năng hoàn thành, kiểm tra tích hợp và mở PR từ nhánh chung về `develop`, tiếp tục yêu cầu Mentor approve. Không merge nhánh cá nhân thẳng vào `develop` khi tác vụ dùng mô hình nhánh chung.

## 4. Release và hotfix

**Release:** tạo `release/v1.0.0` từ `origin/develop`; QA và sửa lỗi nhỏ trên nhánh release. Mở PR về `main`, chờ Mentor approve và các kiểm tra đạt. Sau merge, tạo tag `v1.0.0` tại commit phát hành trên `main`. Mở PR đồng bộ nhánh release về `develop` nếu có thay đổi chưa được tích hợp; nếu không có diff, ghi nhận điều này trong PR phát hành.

**Hotfix:** tạo `hotfix/<mã-tác-vụ>-<tên-ngắn-gọn>` từ `origin/main`; sửa lỗi, kiểm tra và mở PR về `main`. Sau khi được Mentor approve và merge, tạo tag bản vá, đồng thời mở PR đồng bộ hotfix về `develop`. Không bỏ qua review vì tính khẩn cấp.

Luồng phát hành mẫu:

```text
main (Initial Commit)
  -> develop
       -> feature/task-1-rag-baseline
            feat(rag): implement retrieval baseline
            test(rag): correct retrieval expectations
          -> PR + Mentor approve -> develop
       -> release/v1.0.0
            fix(release): correct demo configuration
          -> PR + Mentor approve -> main -> tag v1.0.0
          -> PR + Mentor approve -> develop
```

Các thao tác tích hợp vào `main` và `develop` thực hiện qua PR, không dùng merge/push trực tiếp tại máy cá nhân. Rebase áp dụng cho nhánh công việc để xử lý conflict; không rebase các nhánh ổn định/chung một cách tùy tiện.

## 5. Conventional Commits

```text
<type>(<scope>): <mô tả ngắn>
```

| Type | Dùng khi | Ví dụ |
|---|---|---|
| `feat` | Thêm tính năng | `feat(auth): validate register form inputs` |
| `fix` | Sửa lỗi | `fix(rag): exclude non-base-game chunks` |
| `docs` | Sửa tài liệu | `docs(scope): restrict project to Elden Ring base game` |
| `refactor` | Tổ chức lại code, giữ hành vi | `refactor(api): extract chat service` |
| `test` | Thêm/sửa kiểm thử | `test(rag): cover out-of-scope questions` |
| `chore` | Công việc bảo trì | `chore(deps): update dependency lockfile` |
| `ci` | Sửa quy trình CI | `ci: validate pull requests to develop` |
| `build` | Sửa hệ thống build | `build(docker): cache backend dependencies` |
| `perf` | Tối ưu hiệu năng | `perf(retrieval): batch query embeddings` |

Scope có thể bỏ khi không cần. Dùng `!` hoặc footer `BREAKING CHANGE:` khi có thay đổi không tương thích. Mỗi commit tập trung vào một mục đích; không commit secret, `.env`, dữ liệu crawl hay model weights.

## 6. Điều kiện trước khi merge

- PR đúng nhánh đích, có mã/link tác vụ và mô tả kiểm chứng được.
- Không có conflict; nhánh công việc được rebase và kiểm tra lại khi nhánh nền thay đổi.
- Các kiểm tra CI bắt buộc đạt; thay đổi docs phải kiểm tra link, tính nhất quán và bản sinh tự động.
- Mentor đã review và approve phiên bản thay đổi mới nhất; xử lý các review conversation còn mở.
- Feature hoàn thành khi đã tích hợp vào `develop`; lên Production là một đợt release riêng.
- Cập nhật tài liệu và trạng thái yêu cầu liên quan.

Thiết lập branch protection/ruleset cho `main` và `develop`: yêu cầu PR, kiểm tra CI, review approval và hạn chế bypass/push trực tiếp. Phân công tài khoản Mentor làm reviewer/CODEOWNER để thực thi yêu cầu Mentor approve. Kiểm tra nguồn PR vào `main` chỉ thuộc `release/*` hoặc `hotfix/*` bằng quy trình review hoặc một CI check riêng. File quy ước này không tự cấu hình các thiết lập trên GitHub.

## 7. Nguồn tài liệu và kế hoạch

`planning/sprint_plan.json` là nguồn của kế hoạch sprint. Khi đổi phạm vi hoặc quy trình, sửa JSON trước rồi chạy `python planning/build_docs.py` để đồng bộ `docs/03_SPRINT_PLAN.md` và các bản Word trong `docs/export/`. Không sửa riêng bản sprint được sinh tự động. Cập nhật Trello là thao tác riêng; sinh tài liệu không đồng nghĩa board đã được cập nhật.
