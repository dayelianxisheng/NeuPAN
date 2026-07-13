#!/usr/bin/env python3
"""Generate deterministic primitive-only SDF 1.9 models and frozen worlds."""

from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

MODELS={
 "static_obstacle":("box","<size>1 1 1</size>","0.55 0.55 0.55 1"),
 "static_cylinder":("cylinder","<radius>0.35</radius><length>0.7</length>","0.55 0.55 0.55 1"),
 "human_placeholder":("cylinder","<radius>0.35</radius><length>1.7</length>","0.8 0.55 0.35 1"),
 "vehicle_placeholder":("box","<size>0.8 0.5 0.4</size>","0.25 0.35 0.8 1"),
 "robot_obstacle":("box","<size>0.6 0.45 0.3</size>","0.3 0.7 0.4 1"),
}

ROBOT="""<?xml version='1.0'?>
<sdf version='1.9'><model name='sgcf_diff_drive_robot'><static>false</static>
<link name='base_footprint'/><link name='base_link'><pose relative_to='base_footprint'>0 0 0.1 0 0 0</pose><inertial><mass>20</mass><inertia><ixx>0.5</ixx><iyy>0.8</iyy><izz>1.0</izz></inertia></inertial><collision name='planner_footprint_collision'><geometry><box><size>0.8 0.5 0.2</size></box></geometry><surface><friction><ode><mu>0</mu><mu2>0</mu2></ode></friction></surface></collision><visual name='body'><geometry><box><size>0.8 0.5 0.2</size></box></geometry><material><diffuse>0.15 0.25 0.8 1</diffuse></material></visual></link>
<joint name='base_footprint_to_base_link' type='fixed'><parent>base_footprint</parent><child>base_link</child></joint>
<link name='left_wheel_link'><pose relative_to='base_link'>0 0.25 0 0 0 0</pose><inertial><mass>1</mass><inertia><ixx>0.0027083333333333334</ixx><iyy>0.005</iyy><izz>0.0027083333333333334</izz></inertia></inertial><collision name='left_wheel_collision'><pose>0 -0.025 0 1.5707963267948966 0 0</pose><geometry><cylinder><radius>0.1</radius><length>0.05</length></cylinder></geometry><surface><friction><ode><mu>1</mu><mu2>1</mu2></ode></friction></surface></collision><visual name='left_wheel_visual'><pose>0 -0.025 0 1.5707963267948966 0 0</pose><geometry><cylinder><radius>0.1</radius><length>0.05</length></cylinder></geometry><material><diffuse>0.05 0.05 0.05 1</diffuse></material></visual></link>
<link name='right_wheel_link'><pose relative_to='base_link'>0 -0.25 0 0 0 0</pose><inertial><mass>1</mass><inertia><ixx>0.0027083333333333334</ixx><iyy>0.005</iyy><izz>0.0027083333333333334</izz></inertia></inertial><collision name='right_wheel_collision'><pose>0 0.025 0 1.5707963267948966 0 0</pose><geometry><cylinder><radius>0.1</radius><length>0.05</length></cylinder></geometry><surface><friction><ode><mu>1</mu><mu2>1</mu2></ode></friction></surface></collision><visual name='right_wheel_visual'><pose>0 0.025 0 1.5707963267948966 0 0</pose><geometry><cylinder><radius>0.1</radius><length>0.05</length></cylinder></geometry><material><diffuse>0.05 0.05 0.05 1</diffuse></material></visual></link>
<joint name='left_wheel_joint' type='revolute'><parent>base_link</parent><child>left_wheel_link</child><axis><xyz>0 1 0</xyz><limit><lower>-1e16</lower><upper>1e16</upper><velocity>10</velocity><effort>100</effort></limit></axis></joint>
<joint name='right_wheel_joint' type='revolute'><parent>base_link</parent><child>right_wheel_link</child><axis><xyz>0 1 0</xyz><limit><lower>-1e16</lower><upper>1e16</upper><velocity>10</velocity><effort>100</effort></limit></axis></joint>
<link name='lidar_link'><pose relative_to='base_link'>0 0 0.1 0 0 0</pose><sensor name='lidar' type='gpu_lidar'><always_on>true</always_on><update_rate>10</update_rate><topic>/scan</topic><lidar><scan><horizontal><samples>181</samples><resolution>1</resolution><min_angle>-3.141592653589793</min_angle><max_angle>3.141592653589793</max_angle></horizontal></scan><range><min>0.05</min><max>8.0</max><resolution>0.001</resolution></range><noise><type>gaussian</type><mean>0</mean><stddev>0</stddev></noise></lidar></sensor></link><joint name='lidar_fixed' type='fixed'><parent>base_link</parent><child>lidar_link</child></joint>
<link name='camera_link'><pose relative_to='base_link'>0 0 0.9 0 0 0</pose><sensor name='rgb_camera' type='camera'><always_on>true</always_on><update_rate>10</update_rate><topic>/camera/image_raw</topic><camera><horizontal_fov>1.453284681363431</horizontal_fov><image><width>320</width><height>240</height><format>R8G8B8</format></image><clip><near>0.05</near><far>20</far></clip></camera></sensor></link><joint name='camera_fixed' type='fixed'><parent>base_link</parent><child>camera_link</child></joint>
<frame name='camera_optical_frame' attached_to='camera_link'><pose relative_to='camera_link'>0 0 0 -1.5707963267948966 0 -1.5707963267948966</pose></frame>
<plugin filename='gz-sim-diff-drive-system' name='gz::sim::systems::DiffDrive'><left_joint>left_wheel_joint</left_joint><right_joint>right_wheel_joint</right_joint><wheel_separation>0.5</wheel_separation><wheel_radius>0.1</wheel_radius><odom_publish_frequency>50</odom_publish_frequency><topic>/cmd_vel</topic><odom_topic>/odom</odom_topic><tf_topic>/tf</tf_topic><frame_id>odom</frame_id><child_frame_id>base_link</child_frame_id><max_linear_velocity>1.0</max_linear_velocity><max_angular_velocity>1.5</max_angular_velocity></plugin>
</model></sdf>
"""

WORLD_SYSTEMS="""<plugin filename='gz-sim-physics-system' name='gz::sim::systems::Physics'/><plugin filename='gz-sim-user-commands-system' name='gz::sim::systems::UserCommands'/><plugin filename='gz-sim-scene-broadcaster-system' name='gz::sim::systems::SceneBroadcaster'/><plugin filename='gz-sim-sensors-system' name='gz::sim::systems::Sensors'><render_engine>ogre2</render_engine></plugin>"""

SCENARIOS=[
 ("empty_world",[]),
 ("single_static_obstacle",[("static_01","static_cylinder",[1.5,0,.35,0,0,0],[1,1,1],"STATIC_OBSTACLE")]),
 ("static_corridor",[("wall_left","static_obstacle",[2,.7,.25,0,0,0],[5,.15,.5],"STATIC_OBSTACLE"),("wall_right","static_obstacle",[2,-.7,.25,0,0,0],[5,.15,.5],"STATIC_OBSTACLE")]),
 ("narrow_passage",[("wall_left","static_obstacle",[2,.585,.25,0,0,0],[5,.15,.5],"STATIC_OBSTACLE"),("wall_right","static_obstacle",[2,-.585,.25,0,0,0],[5,.15,.5],"STATIC_OBSTACLE")]),
 ("human_path_center",[("human_01","human_placeholder",[1.5,0,.85,0,0,0],[1,1,1],"HUMAN")]),
 ("human_path_side",[("human_01","human_placeholder",[1.5,.35,.85,0,0,0],[1,1,1],"HUMAN")]),
 ("vehicle_path",[("vehicle_01","vehicle_placeholder",[1.5,0,.2,0,0,0],[1,1,1],"VEHICLE")]),
 ("robot_obstacle",[("robot_obstacle_01","robot_obstacle",[1.5,0,.15,0,0,0],[1,1,1],"ROBOT")]),
 ("semantic_infeasible",[("human_01","human_placeholder",[1.5,0,.85,0,0,0],[1,1,1],"HUMAN")]),
 ("initial_collision",[("initial_collision_obstacle","human_placeholder",[.41,0,.2,0,0,0],[.5714285714285714,.5714285714285714,.23529411764705882],"HUMAN")]),
 ("rgb_dropout_contract",[("human_01","human_placeholder",[1.5,0,.85,0,0,0],[1,1,1],"HUMAN")]),
 ("outdated_rgb_contract",[("human_01","human_placeholder",[1.5,0,.85,0,0,0],[1,1,1],"HUMAN")]),
]

def model_files():
 d=ROOT/"models"/"sgcf_diff_drive_robot"; d.mkdir(parents=True,exist_ok=True); (d/"model.sdf").write_text(ROBOT); (d/"model.config").write_text("<model><name>SGCF Differential Robot</name><version>1.0</version><sdf version='1.9'>model.sdf</sdf></model>\n")
 for name,(shape,geometry,color) in MODELS.items():
  d=ROOT/"models"/name; d.mkdir(parents=True,exist_ok=True); xml=f"<?xml version='1.0'?><sdf version='1.9'><model name='{name}'><static>true</static><link name='body'><collision name='collision'><geometry><{shape}>{geometry}</{shape}></geometry></collision><visual name='visual'><geometry><{shape}>{geometry}</{shape}></geometry><material><diffuse>{color}</diffuse></material></visual></link></model></sdf>\n"; (d/"model.sdf").write_text(xml); (d/"model.config").write_text(f"<model><name>{name}</name><version>1.0</version><sdf version='1.9'>model.sdf</sdf></model>\n")

def world_files():
 for scene,obstacles in SCENARIOS:
  includes=["<include><uri>model://sgcf_diff_drive_robot</uri><name>sgcf_robot</name><pose>0 0 0 0 0 0</pose></include>"]
  for name,model,pose,scale,_ in obstacles: includes.append(f"<include><uri>model://{model}</uri><name>{name}</name><pose>{' '.join(map(str,pose))}</pose><scale>{' '.join(map(str,scale))}</scale></include>")
  ground="<model name='ground_plane'><static>true</static><link name='ground'><collision name='collision'><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></collision><visual name='visual'><geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry></visual></link></model>"
  xml="<?xml version='1.0'?>\n<sdf version='1.9'><world name='"+scene+"'><gravity>0 0 -9.81</gravity>"+WORLD_SYSTEMS+ground+"".join(includes)+"</world></sdf>\n"
  (ROOT/"worlds"/f"{scene}.sdf").write_text(xml)

model_files(); world_files()
print(json.dumps({"sdf_version":"1.9","models":len(MODELS)+1,"worlds":len(SCENARIOS)}))
