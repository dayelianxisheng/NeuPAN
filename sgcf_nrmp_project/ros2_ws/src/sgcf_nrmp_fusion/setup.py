from setuptools import setup
setup(name='sgcf_nrmp_fusion',version='0.1.0',packages=['sgcf_nrmp_fusion'],data_files=[('share/ament_index/resource_index/packages',['resource/sgcf_nrmp_fusion']),('share/sgcf_nrmp_fusion',['package.xml'])],entry_points={'console_scripts':['offline_fusion=sgcf_nrmp_fusion.offline_fusion:main']})
