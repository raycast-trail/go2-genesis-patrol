import math, struct, numpy as np, foxglove
from foxglove import messages as M
from foxglove.channels import LaserScanChannel, PointCloudChannel, FrameTransformChannel, PosesInFrameChannel, SceneUpdateChannel

def ts(t):  # seconds -> Timestamp
    return M.Timestamp(sec=int(t), nsec=int((t % 1) * 1e9))

writer = foxglove.open_mcap("smoke.mcap", allow_overwrite=True)
scan_ch = LaserScanChannel("/lidar/scan"); pc_ch = PointCloudChannel("/lidar/points")
tf_ch = FrameTransformChannel("/tf"); path_ch = PosesInFrameChannel("/trajectory"); scene_ch = SceneUpdateChannel("/obstacles")

# 障害物(静的シーン)
ents = []
for i,(x,y,r) in enumerate([(1.5,0,0.2),(0,-2,0.15)]):
    ents.append(M.SceneEntity(frame_id="world", id=f"obs{i}", timestamp=ts(0),
        cylinders=[M.CylinderPrimitive(pose=M.Pose(position=M.Vector3(x=x,y=y,z=0.3), orientation=M.Quaternion(x=0,y=0,z=0,w=1)),
                                       size=M.Vector3(x=2*r,y=2*r,z=0.6), bottom_scale=1, top_scale=1, color=M.Color(r=0.6,g=0.6,b=0.6,a=1))]))
scene_ch.log(M.SceneUpdate(entities=ents), log_time=0)

poses=[]; angles=np.radians(np.arange(-180,180,5))
for k in range(100):
    t=k*0.02; x=0.5*t; yaw=0.1*t
    # TF world->base
    tf_ch.log(M.FrameTransform(timestamp=ts(t), parent_frame_id="world", child_frame_id="base",
              translation=M.Vector3(x=x,y=0,z=0.3), rotation=M.Quaternion(x=0,y=0,z=math.sin(yaw/2),w=math.cos(yaw/2))), log_time=int(t*1e9))
    d=np.full(72,5.0); d[36]=max(0.1,1.3-x)   # 正面に障害物
    scan_ch.log(M.LaserScan(timestamp=ts(t), frame_id="base", pose=M.Pose(position=M.Vector3(x=0,y=0,z=0.15), orientation=M.Quaternion(x=0,y=0,z=0,w=1)),
                start_angle=float(angles[0]), end_angle=float(angles[-1]), ranges=d.tolist(), intensities=[]), log_time=int(t*1e9))
    # 点群(world 座標、xyz float32)
    pts=np.stack([x+d*np.cos(angles+yaw), d*np.sin(angles+yaw), np.full(72,0.45)],1).astype(np.float32)
    pc_ch.log(M.PointCloud(timestamp=ts(t), frame_id="world", pose=M.Pose(position=M.Vector3(x=0,y=0,z=0), orientation=M.Quaternion(x=0,y=0,z=0,w=1)),
              point_stride=12, fields=[M.PackedElementField(name="x",offset=0,type=M.PackedElementFieldNumericType.Float32),
                                       M.PackedElementField(name="y",offset=4,type=M.PackedElementFieldNumericType.Float32),
                                       M.PackedElementField(name="z",offset=8,type=M.PackedElementFieldNumericType.Float32)],
              data=pts.tobytes()), log_time=int(t*1e9))
    poses.append(M.Pose(position=M.Vector3(x=x,y=0,z=0.3), orientation=M.Quaternion(x=0,y=0,z=math.sin(yaw/2),w=math.cos(yaw/2))))
    path_ch.log(M.PosesInFrame(timestamp=ts(t), frame_id="world", poses=list(poses)), log_time=int(t*1e9))
writer.close()
import os; print("wrote smoke.mcap", os.path.getsize("smoke.mcap"), "bytes")
