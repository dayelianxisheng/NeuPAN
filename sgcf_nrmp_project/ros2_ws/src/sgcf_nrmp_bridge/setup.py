from setuptools import find_packages, setup

package_name = "sgcf_nrmp_bridge"
setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            "share/" + package_name + "/launch",
            [
                "launch/stage11ca_bridge.launch.py",
                "launch/stage11cb_open_loop.launch.py",
            ],
        ),
        (
            "share/" + package_name + "/config",
            [
                "config/stage11ca_bridge.yaml",
                "config/stage11cb_command_profile.yaml",
            ],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="SGCF-NRMP",
    maintainer_email="noreply@example.com",
    description="Stage 11C-A bridge contract audit tools.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "bridge_contract_audit = sgcf_nrmp_bridge.bridge_contract_audit:main",
            "stage11cb_open_loop_audit = sgcf_nrmp_bridge.stage11cb_open_loop_audit:main",
        ]
    },
)
