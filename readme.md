# BlockGaussian

## Scene reconstruction
### Dataset Preprocess
#### Preprocess Mill-19 dataset and UrbanScene3D dataset

#### Preprocess MatrixCity dataset

#### Preprocess costumed dataset

### Estimate depth maps of training-views(Optional)
1. Download DepthAnythingV2 checkpoints and put it under `preprocess/Depth-Anything-V2/checkpoints`
2. Estimate depth maps and depth-aligning parameters
``` shell
python preprocess/estimate_depth_and_rescale.py -s datasets/scene_dirpath
```

### Scene partition and view assignment
1. 配置`scene.yaml`文件

2. 进行场景划分
``` shell
python scene_partition.py -c ./configs/scene.yaml
```

### Training
1. Training on single GPU
```shell
python train.py -c ./configs/scene.yaml
```

&emsp;**--config / -c** : 

&emsp;**--blocks_id / -b** : block ids need to reconstruction


2. Training on multi-GPU platform

```shell
python parallel_train.py
```



### Postfix and merge block results
```shell
python block_fusion.py -o ./output/rubble --merge
```


## Render views
### Render train/test views
```shell
python render_views.py -o ./output/scene_name --train_eval_split --eval_only
```

&emsp;**--train_eval_split** : train and eval views are stored separately

&emsp;**--eval_only** : only render eval views


### Interactive Rendering

Using SIBR_Viewer to interactively render the novel views


## Evaluation
```shell
python metrics.py -o ./output/scene_name --train_eval_split --eval_only
```

&emsp;**--train_eval_split** : train and eval views are stored separately

&emsp;**--eval_only** : only render eval views
