from setuptools import setup
setup(name='sgcf_nrmp_planner',version='0.1.0',packages=['sgcf_nrmp_planner'],data_files=[('share/ament_index/resource_index/packages',['resource/sgcf_nrmp_planner']),('share/sgcf_nrmp_planner',['package.xml'])],entry_points={'console_scripts':['offline_planner=sgcf_nrmp_planner.offline_planner:main']})
