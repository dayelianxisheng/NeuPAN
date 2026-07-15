from setuptools import setup
setup(name='sgcf_nrmp_evaluation',version='0.1.0',packages=['sgcf_nrmp_evaluation'],data_files=[('share/ament_index/resource_index/packages',['resource/sgcf_nrmp_evaluation']),('share/sgcf_nrmp_evaluation',['package.xml'])],entry_points={'console_scripts':['offline_diagnostics=sgcf_nrmp_evaluation.offline_diagnostics:main']})
