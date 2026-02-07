#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess



GH_PAT = os.environ.get("GH_PAT", "").strip()
OWNER = "rtTechClark"

def repo_url(repo_name: str, pat: str) -> str:
    # 采用你指定的 oauth2 PAT 方式
    return f"https://oauth2:{pat}@github.com/{OWNER}/{repo_name}.git"

def run(cmd, cwd=None):
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(e.returncode)

def ensure_clean_dir(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

def project_root() -> str:
    # 本脚本位于 .github/workflow/，上两级为项目根
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def detect_remote_ref_kind(url: str, ref: str):
    # 检查远端是否存在指定的 tag 或 branch，并返回其类型
    if not ref:
        return None
    def ls(pattern: str) -> bool:
        try:
            p = subprocess.run(
                ["git", "ls-remote", url, pattern],
                check=True, capture_output=True, text=True,
            )
            return bool(p.stdout.strip())
        except subprocess.CalledProcessError:
            return False
    if ls(f"refs/tags/{ref}"):
        return "tag"
    if ls(f"refs/heads/{ref}"):
        return "branch"
    return None

def clone_repo(repo_name: str, target_dir: str, ref=None):
    pat = GH_PAT
    if not pat:
        print("GH_PAT is empty; cannot clone private repos.", file=sys.stderr)
        sys.exit(1)
    url = repo_url(repo_name, pat)
    msg = f"Cloning {OWNER}/{repo_name} -> {target_dir}" + (f" @ {ref}" if ref else "")
    print(msg)

    ensure_clean_dir(target_dir)

    # 分辨 ref 类型：branch 用 --branch，tag 用精确 fetch+checkout
    kind = detect_remote_ref_kind(url, ref) if ref else None
    if kind == "branch":
        run(["git", "clone", "--depth", "1", "--branch", ref, url, target_dir])
        return

    # 默认先完整克隆（避免标签指向的提交不在默认分支历史时缺对象）
    run(["git", "clone", url, target_dir])

    if kind == "tag":
        # 精确抓取该标签引用，确保对象到位，然后检出标签
        run(["git", "-C", target_dir, "fetch", "--depth", "1", "origin", f"refs/tags/{ref}:refs/tags/{ref}"])
        run(["git", "-C", target_dir, "checkout", "-f", f"tags/{ref}"])
        print(f"Checked out tag {ref} in {target_dir}")
        return

    if ref:
        # 回退逻辑：尝试可用标签/分支名直接检出（适配轻量/注释标签命名）
        try:
            # 拉全标签，兼容某些服务器不返回所有 tags 的情况
            run(["git", "-C", target_dir, "fetch", "--tags"])
        except Exception:
            pass
        try:
            run(["git", "-C", target_dir, "checkout", ref])
            print(f"Checked out {ref} in {target_dir}")
        except SystemExit:
            print(
                f"Warning: ref '{ref}' not found for {OWNER}/{repo_name}. "
                f"Stayed on default branch HEAD.",
                file=sys.stderr,
            )
    else:
        run(["git", "clone", url, target_dir])

def load_config(root: str):
    cfg_path_env = os.environ.get("REPO_CONFIG_JSON", "").strip()
    cfg_path = cfg_path_env if cfg_path_env else os.path.join(root, ".github", "workflows", "repos.json")
    if not os.path.exists(cfg_path):
        print(f"Config file not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"Failed to read config JSON: {e}", file=sys.stderr)
        sys.exit(1)
    if "repos" not in cfg or not isinstance(cfg["repos"], list):
        print("Invalid config: missing 'repos' array", file=sys.stderr)
        sys.exit(1)
    return cfg

def remote_ref_exists(url: str, ref: str) -> bool:
    if not ref:
        return False
    try:
        # 检查 heads 和 tags，命中则返回
        p = subprocess.run(
            ["git", "ls-remote", "--heads", "--tags", url, ref],
            check=True,
            capture_output=True,
            text=True,
        )
        return bool(p.stdout.strip())
    except subprocess.CalledProcessError:
        return False

def copy_build_script(root: str, source_root: str):
    src = os.path.join(root, "build_rp2_cmd.sh")
    dst = os.path.join(source_root, "build_rp2_cmd.sh")
    if not os.path.exists(src):
        print(f"Warning: build script not found: {src}", file=sys.stderr)
        return
    shutil.copyfile(src, dst)
    # 赋予可执行权限
    try:
        os.chmod(dst, 0o755)
    except Exception as e:
        print(f"Warning: failed to chmod +x on {dst}: {e}", file=sys.stderr)
    print(f"Copied build_rp2_cmd.sh -> {dst}")

def main():
    root = project_root()
    cfg = load_config(root)

    # 如果配置里指定了 owner，覆盖默认 OWNER
    global OWNER
    OWNER = cfg.get("owner", OWNER)

    for item in cfg["repos"]:
        repo = item.get("repo", "").strip()
        target = item.get("target", "").strip()
        ref = (item.get("tag", "") or "").strip() or None
        if not repo or not target:
            print(f"Invalid repo item: {item}", file=sys.stderr)
            sys.exit(1)
        target_dir = os.path.join(root, target)
        # 确保父目录存在（如 ports、modules 等）
        os.makedirs(os.path.dirname(target_dir), exist_ok=True)
        clone_repo(repo, target_dir, ref)

    # 克隆完成后，把 build_rp2_cmd.sh 复制到 rtTechMPY-Source 根目录
    source_target = next((it.get("target", "") for it in cfg["repos"] if it.get("repo", "") == "rtTechMPY-Source"), None)
    if source_target:
        source_root = os.path.join(root, source_target)
        copy_build_script(root, source_root)
    else:
        print("Warning: rtTechMPY-Source not found in config; skip copying build script.", file=sys.stderr)

    print("All repositories cloned and arranged successfully.")

if __name__ == "__main__":
    main()
