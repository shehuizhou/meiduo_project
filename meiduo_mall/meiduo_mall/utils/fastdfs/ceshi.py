from fdfs_client.client import Fdfs_client
client = Fdfs_client('./client.conf')
# 3. 调用FastDFS客户端上传文件方法
ret = client.upload_by_filename('/home/python/Desktop/01.jpeg')
print(ret)





'''
{'Group name': 'group1', 
'Remote file_id': 'group1/M00/00/00/wKgTjFzOlyGAIgyoAAC4j90Tziw09.jpeg', 
'Status': 'Upload successed.',
'Local file name': '/home/python/Desktop/01.jpeg',
'Uploaded size': '46.00KB', 
'Storage IP': '192.168.19.140'}
'''