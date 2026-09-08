#!/usr/bin/env python3
"""English, image-first trial figure. Read local records only; no robot RPC."""
import json
import subprocess
import difflib
import hashlib
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch
from matplotlib.ticker import MaxNLocator
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/labB'
JST = timezone(timedelta(hours=9))


def recovered_patches():
    """Reverse the two literal apply_patch edits preserved in this conversation.

    Timestamp is the first audit invocation proving availability, not a claimed
    exact edit time. Earlier unrecorded edits are intentionally not imputed.
    """
    current=(ROOT/'src/labb_right_cap_control.py').read_text()
    before_twist=current
    for line in ['from scipy.optimize import least_squares\n',
                 'from scipy.spatial.transform import Rotation\n']:
        assert before_twist.count(line)==1
        before_twist=before_twist.replace(line,'',1)
    a=before_twist.index('\n\ndef world_z_twist_joint_delta(')
    b=before_twist.index('\n\ndef main():',a)
    before_twist=before_twist[:a]+before_twist[b:]
    a=before_twist.index('    twist = sub.add_parser("twist-world-z")\n')
    b=before_twist.index('    ratchet = sub.add_parser',a)
    before_twist=before_twist[:a]+before_twist[b:]
    a=before_twist.index('        elif args.command == "twist-world-z":\n')
    b=before_twist.index('        elif args.command == "ratchet-unscrew":',a)
    before_twist=before_twist[:a]+before_twist[b:]
    before_hold=before_twist
    replacements=[
        ('def position_joint_delta(q, delta_xyz, max_joint_delta=0.18, hold_wrist=False):',
         'def position_joint_delta(q, delta_xyz, max_joint_delta=0.18):'),
        ('    active_joints = 3 if hold_wrist else 5\n    jacobian = np.empty((3, active_joints))\n    for axis in range(active_joints):',
         '    jacobian = np.empty((3, 5))\n    for axis in range(5):'),
        ('    delta = np.r_[dq5, np.zeros(6 - active_joints)]','    delta = np.r_[dq5, 0.0]'),
        ('    plan_position.add_argument("--hold-wrist", action="store_true")\n',''),
        ('    move_position.add_argument("--hold-wrist", action="store_true")\n',''),
        ('before["q_rad"], args.delta_xyz, args.max_joint_delta, args.hold_wrist',
         'before["q_rad"], args.delta_xyz, args.max_joint_delta'),
        ('initial["q_rad"], args.delta_xyz, args.max_joint_delta, args.hold_wrist',
         'initial["q_rad"], args.delta_xyz, args.max_joint_delta')]
    for old,new in replacements:
        assert before_hold.count(old)==1,old
        before_hold=before_hold.replace(old,new,1)
    versions=[before_hold,before_twist,current]
    dest=BASE/'recovered_code_history'
    dest.mkdir(exist_ok=True)
    for name,source in zip(['before_wrist_hold','after_wrist_hold','after_world_z_twist'],versions):
        ast.parse(source)
        (dest/(name+'.py')).write_text(source)
    result=[]
    for name,clock,old,new in zip(['wrist_hold','world_z_twist'],['21:53:03.230742','21:57:22.402661'],versions,versions[1:]):
        diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='before.py',tofile='after.py'))
        (dest/(name+'.patch')).write_text(diff)
        added=sum(s.startswith('+') and not s.startswith('+++') for s in diff.splitlines())
        deleted=sum(s.startswith('-') and not s.startswith('---') for s in diff.splitlines())
        assert len(new.splitlines())-len(old.splitlines())==added-deleted
        result.append({'event':name,'confirmed_by_local_time':clock,'added':added,'deleted':deleted,
                       'net':added-deleted,'before_lines':len(old.splitlines()),'after_lines':len(new.splitlines()),
                       'before_sha256':hashlib.sha256(old.encode()).hexdigest(),
                       'after_sha256':hashlib.sha256(new.encode()).hexdigest(),
                       'source':'Literal apply_patch operations in this conversation; reversed against unchanged controller source',
                       'patch':str((dest/(name+'.patch')).relative_to(ROOT))})
    (dest/'events.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    def read(p): return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
    def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).splitlines()
    start = datetime(2026,9,8,21,11,17,tzinfo=JST).timestamp()
    end = datetime(2026,9,8,22,0,0,tzinfo=JST).timestamp()
    def x(t): return (t-start)/60
    def at(t): return x(datetime.fromisoformat('2026-09-08T'+t+'+09:00').timestamp())
    def stamp(r): return datetime.fromisoformat(r['utc']).timestamp()
    audit=[r for r in read(BASE/'right_cap_commands.jsonl') if start<=stamp(r)<=end]
    pressure=[r for r in read(BASE/'right_pressure_remaining.jsonl') if start<=r['time_unix_s']<=end]
    times=np.array([r['time_unix_s'] for r in pressure])
    effort=np.array([r['right_gripper_effort_Nm'] for r in pressure])
    assert np.all(np.diff(times)>0) and np.isfinite(effort).all()
    recovered=recovered_patches()
    counts=[]
    for group,paths in [('Modified',git('diff','HEAD','--name-only')),
                        ('New',git('ls-files','--others','--exclude-standard','src','robot','rollout','tests'))]:
        for p in paths:
            if Path(p).suffix in {'.py','.sh'} and not Path(p).name.startswith('plot_labb_timeline'):
                counts.append({'path':p,'group':group,'physical_lines':len((ROOT/p).read_text().splitlines())})
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False})
    metrics=json.loads((BASE/'session_usage_metrics.json').read_text())
    fig=plt.figure(figsize=(28,22),facecolor='white')
    initial=BASE/'current/2026-09-08/20260908T121117.585065Z_head_initial_head_1df57cc7/derived'
    images=[(initial/'head_rgb_landscape.png','A  Start'),
            (initial/'cap_detection.png','B  Target label'),
            (BASE/'current/2026-09-08/device1_right_motion_overlay.png','C  Motion mask'),
            (BASE/'current/2026-09-08/20260908T125923.932896Z_left_detached_check_orth_c57afcda/derived/head_rgb_landscape.png','D  Cap grasp')]
    image_axes=[]
    for i,(p,label) in enumerate(images):
        ax=fig.add_axes([.037+i*.243,.735,.229,.205])
        ax.imshow(plt.imread(p)); ax.axis('off'); ax.set_title(label,loc='left',fontsize=14,pad=12)
        image_axes.append(ax)
    gs=fig.add_gridspec(5,1,left=.22,right=.97,top=.685,bottom=.04,height_ratios=[3.4,1.2,1.2,1.2,1.2],hspace=.28)
    axes=[fig.add_subplot(gs[i]) for i in [1,2,3,4,0]]
    clocks=['21:15:00','21:20:00','21:25:00','21:30:00','21:35:00','21:40:00','21:45:00','21:50:00','21:55:00','22:00:00']
    for ax in axes:
        ax.set_xlim(0,x(end)); ax.set_xticks([at(t) for t in clocks]); ax.tick_params(axis='x',labelbottom=False,bottom=False)
        ax.grid(axis='x',color='#e3e8ed',lw=.7)
    sparse=[r for r in audit if r.get('before') and 'gripper_effort_Nm' in r['before'] and stamp(r)<times[0]]
    axes[0].scatter([x(stamp(r)) for r in sparse],[r['before']['gripper_effort_Nm'] for r in sparse],s=12,color='#b84364',label='Pre-command samples')
    axes[0].scatter(x(times),effort,s=12,color='#b84364',edgecolors='none')
    axes[0].axhline(0,color='#adb5c0',lw=.6); axes[0].set_ylim(-1.28,.45)
    axes[0].set_yticks([-1,0])
    axes[0].set_ylabel('Gripper\neffort (N·m)')
    obs=[r for r in audit if r.get('before') and 'gripper_open_ratio' in r['before']]
    grips=[r for r in audit if r['command']=='grip-sweep']
    axes[1].scatter([x(stamp(r)) for r in obs],[r['before']['gripper_open_ratio'] for r in obs],s=13,color='#218494',label='Measured opening')
    axes[1].set_ylim(-.05,1.1); axes[1].set_ylabel('Gripper\nopening')
    axes[1].set_yticks([0,1],['0','1'])
    snapshots=[]
    for path in sorted((BASE/'current/2026-09-08').glob('*/manifest.json')):
        data=json.loads(path.read_text())
        t=datetime.fromisoformat(data['created_at_utc'].replace('Z','+00:00')).timestamp()
        if not start<=t<=end: continue
        paths={p for p in data.get('repository',{}).get('dirty_paths',[])
               if Path(p).suffix in {'.py','.sh'} and not Path(p).name.startswith('plot_labb_timeline')}
        snapshots.append((t,paths))
    selected=[
        'src/labb_right_cap_control.py','src/detect_culture_bottle_cap.py',
        'src/sample_record3d_depth.py','src/estimate_frame_motion.py',
        'src/log_right_pressure.py','rollout/verify_right_home_level.py',
        'src/orient_record3d_frame.sh','tests/test_piper_native_gripper.py']
    first_use=[]
    for path in selected:
        record=next(r for r in metrics['files'] if r['path']==path)
        kind='first_execution' if 'first_execution' in record else 'first_review'
        evidence=record[kind]
        t=datetime.fromisoformat(evidence['utc'].replace('Z','+00:00')).timestamp()
        first_use.append({'path':path,'physical_lines':len((ROOT/path).read_text().splitlines()),
                          'counted_at':datetime.fromtimestamp(t,JST).isoformat(),
                          'minutes':max(0,x(t)),'kind':kind,'evidence':evidence})
    first_use.sort(key=lambda row:row['minutes'])
    sx=sorted({0.0,*[r['minutes'] for r in first_use],x(end)})
    net_files=[sum(r['minutes']<=t for r in first_use) for t in sx]
    net_lines=[sum(r['physical_lines'] for r in first_use if r['minutes']<=t) for t in sx]
    assert net_files[-1]==8 and net_lines[-1]==sum(r['physical_lines'] for r in first_use)
    executed_files=[sum(r['minutes']<=t and r['kind']=='first_execution' for r in first_use) for t in sx]
    executed_lines=[sum(r['physical_lines'] for r in first_use if r['minutes']<=t and r['kind']=='first_execution') for t in sx]
    axes[2].step(sx,executed_files,where='post',color='#527b9e',lw=1.6,label='First execution')
    axes[2].set_ylabel('File change\n(files)'); axes[2].set_yticks([0,2,5]); axes[2].set_ylim(-.3,6)
    tx=[max(0,x(datetime.fromisoformat(r['utc'].replace('Z','+00:00')).timestamp())) for r in metrics['tokens']]
    axes[3].step(tx,[r['total_tokens']/1e6 for r in metrics['tokens']],where='post',color='#795a9b',lw=1.5)
    axes[3].set_ylabel('Tokens\n(million)'); axes[3].set_ylim(0,28)
    axes[3].set_yticks([0,10,20])
    ax=axes[4]; ax.set_ylim(-.6,.6); ax.set_yticks([0],['Operation'])
    spans=[
        ('21:11:17','21:15:23',0,'Inspection','#edf0f4'),
        ('21:15:23','21:21:15',0,'Calibration','#dce7ef'),
        ('21:21:15','21:25:23',0,'Approach','#e0ece5'),
        ('21:25:23','21:32:32',0,'Alignment','#dce9ef'),
        ('21:32:32','21:40:57',0,'Grasp attempts','#f1dce4'),
        ('21:40:57','21:41:36',0,'Retreat','#e8e2d7'),
        ('21:41:36','21:45:26',0,'Reorientation','#e5dff0'),
        ('21:45:26','21:51:38',0,'Alignment','#dce9ef'),
        ('21:51:38','21:53:12',0,'Reorientation','#e5dff0'),
        ('21:53:12','21:55:33',0,'Alignment','#dce9ef'),
        ('21:55:33','21:57:22',0,'Grasp','#f1dce4'),
        ('21:57:22','21:58:47',0,'Rotation','#e5dff0'),
        ('21:58:47','22:00:00',0,'Lift','#deece3')]
    for a,b,y,label,color in spans:
        ax.barh(y,at(b)-at(a),left=at(a),height=.74,color=color,edgecolor='white')
        # Narrow phases need a separate label height to keep doubled text apart.
        label_y=.40 if label=='Retreat' else 0
        ax.text((at(a)+at(b))/2,label_y,label,ha='center',va='center',fontsize=9,rotation=90)
    for axis in axes:
        axis.yaxis.label.set_fontsize(9)
        axis.yaxis.label.set_rotation(0)
        axis.yaxis.label.set_horizontalalignment('right')
        axis.yaxis.label.set_verticalalignment('center')
        axis.yaxis.labelpad=18
    image_clocks=['21:11:17.585065','21:11:17.585065','21:18:26.562516','21:59:23.932896']
    marker_colors=['#66758c','#66758c','#b09921','#805784']
    for i,(pic,clock,color) in enumerate(zip(image_axes,image_clocks,marker_colors)):
        marker_x=at(clock)
        connector=ConnectionPatch(xyA=(.5,0),coordsA=pic.transAxes,
                                  xyB=(marker_x,1),coordsB=axes[4].get_xaxis_transform(),
                                  color=color,lw=1.3,alpha=.85,clip_on=False)
        fig.add_artist(connector)
        if i != 1:
            for axis in axes:
                axis.axvline(marker_x,color=color,lw=1.4,alpha=.75,zorder=5)
            axes[4].text(marker_x,1.015,'A / B' if i==0 else 'CD'[i-2],
                         transform=axes[4].get_xaxis_transform(),ha='left' if i==0 else 'center',
                         va='bottom',fontsize=10,color=color)
    from matplotlib.text import Text
    for text in fig.findobj(match=Text):
        text.set_fontsize(text.get_fontsize()*4)
    output=BASE/'timeline_pressure_tool_changes.png'
    fig.savefig(output,dpi=160,facecolor='white'); plt.close(fig)
    report={'images':[{'path':str(p.relative_to(ROOT)),'label':label} for p,label in images],
            'code_snapshot':counts,'code_count_scope':'Current HEAD diff and untracked Python/shell source, not a historical 22:00 snapshot',
            'pressure_samples':len(pressure),'end_jst':'2026-09-08T22:00:00+09:00',
            'image_times_jst':image_clocks,
            'motion_overlay_source':'current/2026-09-08/20260908T121826.562516Z_right_probe_y_plus20_device1_d278c714/derived/head_rgb_landscape.png',
            'growth':{'minutes':sx,'net_files':net_files,'net_lines':net_lines,'first_use_events':first_use,
                      'executed_files':executed_files,'executed_lines':executed_lines,
                      'recovered_patches':recovered,
                      'method':'Current file sizes counted at first logged execution. Review-only files excluded from plotted curves. Only actual pre-window events clipped to start. No patch double counting.'},
            'tokens':{'source':metrics['source'],'last':metrics['tokens'][-1],
                      'definition':metrics['token_definition']},
            'caveat':'Final image is 37 seconds before cutoff. Cap grasp does not imply cap removal.',
            'output':str(output)}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
