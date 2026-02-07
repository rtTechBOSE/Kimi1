import os
import subprocess
import sys
import hashlib
import zipfile
import tempfile
from datetime import datetime

def _md5_of_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def _collect_md5_targets(dir_path):
    targets = []
    for name in os.listdir(dir_path):
        if name.endswith('.py') or name.endswith('.csv') or name.endswith('.json'):
            targets.append(name)
    return sorted(targets)

def _read_md5_file(md5_path):
    mapping = {}
    if not os.path.exists(md5_path):
        return mapping
    with open(md5_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or '=' not in line:
                continue
            fname, digest = line.split('=', 1)
            mapping[fname.strip()] = digest.strip()
    return mapping

def _write_md5_file(md5_path, mapping):
    lines = []
    for fname in sorted(mapping.keys()):
        lines.append(f"{fname}={mapping[fname]}\n")
    with open(md5_path, 'w') as f:
        f.writelines(lines)

def _compute_current_md5_map(dir_path):
    files = _collect_md5_targets(dir_path)
    return {fname: _md5_of_file(os.path.join(dir_path, fname)) for fname in files}

def _maps_equal(a, b):
    return a == b

def _compile_py_files(fw_upload_dir, mpy_cross_path, mpy_out_dir):
    success_count = 0
    fail_count = 0
    for filename in os.listdir(fw_upload_dir):
        if filename.endswith('.py'):
            if filename == 'boot.py':
                continue
            py_file = os.path.join(fw_upload_dir, filename)
            mpy_file = os.path.join(mpy_out_dir, filename.replace('.py', '.mpy'))
            print(f"Compiling {filename}...", end=" ", flush=True)
            try:
                result = subprocess.run(
                    [mpy_cross_path, py_file, '-o', mpy_file],
                    capture_output=True,
                    text=True,
                    cwd=fw_upload_dir
                )
                if result.returncode == 0:
                    print("OK")
                    success_count += 1
                else:
                    print("FAILED")
                    if result.stderr:
                        print(f"\n  Error: {result.stderr.strip()}")
                    else:
                        print(f"\n  Return code: {result.returncode}")
                    fail_count += 1
            except Exception as e:
                print(f"ERROR: {e}")
                fail_count += 1
    return success_count, fail_count

def _write_version(version_path, prefix=None):
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    value = f"{prefix or 'fw_upload_to_pyboard_'}{ts}"
    with open(version_path, 'w') as f:
        f.write(value)
    return value

def _zip_outputs(fw_upload_dir, zip_output_path, mpy_out_dir):
    with zipfile.ZipFile(zip_output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for name in os.listdir(fw_upload_dir):
            if name.endswith('.json') or name.endswith('.txt') or name.endswith('.csv'):
                full = os.path.join(fw_upload_dir, name)
                zf.write(full, arcname=name)
        if os.path.exists(mpy_out_dir):
            for name in os.listdir(mpy_out_dir):
                if name.endswith('.mpy'):
                    full = os.path.join(mpy_out_dir, name)
                    zf.write(full, arcname=name)
        boot_py = os.path.join(fw_upload_dir, 'boot.py')
        if os.path.exists(boot_py):
            zf.write(boot_py, arcname='boot.py')

def build_mpy():
    # Absolute paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mpy_cross_path = os.path.join(current_dir, "mpy-cross")
    fw_upload_dir = os.path.join(current_dir, "fw_upload_to_pyboard")
    tmpdir_obj = tempfile.TemporaryDirectory()
    mpy_out_dir = tmpdir_obj.name
    
    # Check if mpy-cross exists
    if not os.path.exists(mpy_cross_path):
        print(f"Error: mpy-cross not found at {mpy_cross_path}")
        return

    # Ensure executable permission
    try:
        os.chmod(mpy_cross_path, 0o755)
    except Exception as e:
        print(f"Warning: Could not set executable permission on mpy-cross: {e}")

    # Check if target dir exists
    if not os.path.exists(fw_upload_dir):
        print(f"Error: Target directory not found at {fw_upload_dir}")
        return
    # mpy_out_dir is a temporary directory; no persistent output

    md5_path = os.path.join(fw_upload_dir, 'md5.txt')
    version_path = os.path.join(fw_upload_dir, 'version.txt')
    zip_output_path = os.path.join(os.path.dirname(fw_upload_dir), 'fw_upload_to_pyboard.zip')

    print(f"Build context:")
    print(f"Tool: {mpy_cross_path}")
    print(f"Target: {fw_upload_dir}")
    print("-" * 50)

    existing_map = _read_md5_file(md5_path)
    current_map = _compute_current_md5_map(fw_upload_dir)

    need_rebuild_md5 = not existing_map or not _maps_equal(existing_map, current_map)
    need_rebuild_zip = not os.path.exists(zip_output_path)
    need_rebuild = need_rebuild_md5 or need_rebuild_zip

    if need_rebuild:
        if need_rebuild_zip and not need_rebuild_md5:
            print("压缩包不存在：执行完整流程（编译/更新/压缩）")
        else:
            print("MD5变更或缺失：开始编译并更新元数据")
        success_count, fail_count = _compile_py_files(fw_upload_dir, mpy_cross_path, mpy_out_dir)
        _write_md5_file(md5_path, current_map)
        new_version = None
        try:
            if os.path.exists(version_path):
                with open(version_path, 'r') as vf:
                    content = vf.read().strip()
                    if content:
                        new_version = content
            if not new_version:
                new_version = _write_version(version_path)
        except Exception:
            new_version = _write_version(version_path)
        _zip_outputs(fw_upload_dir, zip_output_path, mpy_out_dir)
        print("-" * 50)
        print(f"编译完成 成功: {success_count}, 失败: {fail_count}")
        print(f"版本号: {new_version}")
        print(f"ZIP输出: {zip_output_path}")
        tmpdir_obj.cleanup()
    else:
        print("MD5一致：跳过编译、版本更新与压缩")

if __name__ == "__main__":
    build_mpy()
