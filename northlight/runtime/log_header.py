from northlight.runtime.runtime_info import get_runtime_info


def build_header() -> str:
    info = get_runtime_info()

    return "\n".join(
        [
            "========== RUN DETAIL ==========",
            f"Version : {info['version']}",
            f"Commit  : {info['commit']}",
            f"Run ID  : {info['run_id']}",
            "================================",
            # "",
        ]
    )
