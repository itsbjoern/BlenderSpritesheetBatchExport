import os
import sys
import math
import argparse
import subprocess
import copy

def startProcess(blenderPath):
    blender = blenderPath

    subprocess.call([
      blender + ' -b RenderSetup.blend --python batchexport.py -- --mode render 1> nul'
    ], shell=True)

def printProgress(curr, maxItems, append='', end=False):
        width = 40
        step = width / maxItems
        bar = '[{}{}]'.format('#' * math.floor(step * curr), ' ' * math.ceil(step * (maxItems - curr)))
        prog = ' {}%'.format(int((100 / maxItems) * curr))

        endCap = '\r' if not end else '\n'
        print(bar + prog + ' - ' + append, file=sys.stderr, end=endCap)

def batchRender(renderObjectsDir, outputDir):
    import bpy

    cwd = os.getcwd()
    renderObjectsDir = renderObjectsDir
    outputDir = outputDir

    outputPath = os.path.join(cwd, outputDir)

    bpy.context.scene.render.resolution_x = 128
    bpy.context.scene.render.resolution_y = 128

    scn = bpy.context.scene

    for (root, dirs, files) in os.walk(os.path.join(cwd, renderObjectsDir)):
        files = [f for f in files if f.endswith('.blend')]

        print('Rendering {} objects'.format(len(files)), file=sys.stderr)

        for (index, filename) in enumerate(files):
            objectPath = os.path.join(cwd, renderObjectsDir, filename)
            objectName = filename.split('.')[0]

            with bpy.data.libraries.load(objectPath, link=False) as (data_from, data_to):
                data_to.actions = [action for action in data_from.actions]
                data_to.objects = [name for name in data_from.objects]

            # Set link objects and set actions
            longestAnim = 0
            for obj in data_to.objects:
              if obj is not None and not obj.type == 'CAMERA' and not obj.type == 'LAMP':
                for action in data_to.actions:
                    longestAnim = max(longestAnim, int(action.frame_range[1]))
                scn.objects.link(obj)

            fileOutputPath = os.path.join(outputPath, objectName)
            os.makedirs(fileOutputPath, exist_ok=True)

            print('Rendering now: {} ({}/{})'.format(objectName, index + 1, len(files)), file=sys.stderr)

            cameraNode = bpy.data.objects['CameraNode']
            camera = bpy.data.objects['Camera']
            framesRotation = scn.frame_end + 1
            framesAnimation = longestAnim + 1
            newEnd = framesRotation * framesAnimation

            scn.frame_set(0)

            # Save camera position, we will need it soon
            orig_pos = copy.deepcopy(camera.matrix_world)
            orig_pos_node = copy.deepcopy(cameraNode.matrix_world)

            # render frames
            for i in range(framesRotation):
                camera.matrix_world = orig_pos
                cameraNode.matrix_world = orig_pos_node

                scn.frame_set(i)

                orig_pos = copy.deepcopy(camera.matrix_world)
                orig_pos_node = copy.deepcopy(cameraNode.matrix_world)

                newName = os.path.join(fileOutputPath, objectName)

                if longestAnim != 0:
                    for j in range(framesAnimation):
                        scn.frame_set(j)

                        # HACK: Reset the camera position for each animation frame
                        camera.matrix_world = orig_pos
                        cameraNode.matrix_world = orig_pos_node

                        # basename is appended with first the per object animation frames and then rotation
                        newName = os.path.join(fileOutputPath, objectName)
                        newName += '_{}'.format(str(i).zfill(4))
                        newName += '_{}'.format(str(j).zfill(2))

                        bpy.context.scene.render.filepath = newName
                        bpy.ops.render.render(write_still=True)

                        printProgress(i * framesAnimation + j, newEnd, append='({}/{}) Frames'.format(i * framesAnimation + j + 1, newEnd))

                    # HACK CONTINUED:
                    # Keyframes always execute the next queued action
                    # so we have to execute it the remaining amount of times to reset the rotation to its initial state
                    # TODO: Better handling in case of rotation having less frames than the animation
                    for j in range(framesRotation - framesAnimation):
                        scn.frame_set(j)
                        camera.matrix_world = orig_pos
                        cameraNode.matrix_world = orig_pos_node
                else:
                    # basename is only appended with rotation frames
                    newName = os.path.join(fileOutputPath, objectName)
                    newName += '_{}'.format(str(i).zfill(4))

                    bpy.context.scene.render.filepath = newName
                    bpy.ops.render.render(write_still=True)

                    printProgress(i, newEnd)

            printProgress(1, 1, end=True)

            # clean up scene by deleting objects
            bpy.ops.object.select_all(action='DESELECT')
            for obj in scn.objects:
              # ignore CameraNode as it isn't a Camera but required for the animation
              if obj.name == 'CameraNode':
                continue

              if not obj.type == 'CAMERA' and not obj.type == 'LAMP':
                  bpy.data.objects[obj.name].select = True
            bpy.ops.object.delete()

def compressImages(outputDir):
    from PIL import Image

    print('Compressing Files')

    cwd = os.getcwd()
    dirPaths = os.path.join(cwd, outputDir)
    for (root, dirs, files) in os.walk(dirPaths):
        for (index, directory) in enumerate(dirs):
            print('Compressing now: {} ({}/{})'.format(directory, index + 1, len(dirs)))
            filePath = os.path.join(dirPaths, directory)
            for (root, dirs, files) in os.walk(filePath):
                for curr in files:
                    currPath = os.path.join(filePath, curr)
                    curr = Image.open(currPath)
                    curr.save(currPath, optimize=True, quality=5)
                    curr.close()

parser = argparse.ArgumentParser()

parser.add_argument('--mode', '-m', default='start', help=argparse.SUPPRESS)

parser.add_argument('--compress', '-c', action='store_true')
parser.set_defaults(compress=False)

parser.add_argument('--renderObjectsDir', '-rd', default='RenderObjects')
parser.add_argument('--outputDir', '-o', default='Output')

parser.add_argument('--blenderPath', '-b', default='/Applications/Blender/blender.app/Contents/MacOS/blender')

newArgv = sys.argv[1:]
if '--' in newArgv:
  ind = newArgv.index('--')
  newArgv = newArgv[(ind + 1):]
args = parser.parse_args(newArgv)

if args.mode == 'start':
    startProcess(args.blenderPath)
    if args.compress:
        compressImages(args.outputDir)
elif args.mode == 'render':
    batchRender(args.renderObjectsDir, args.outputDir)
