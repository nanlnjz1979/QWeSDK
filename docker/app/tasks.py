from celery_app import app
import subprocess
import tempfile
import os
import sys
import time

@app.task(bind=True)
def run_code(self, program_id, code, language='python'):
    """
    运行指定代码的任务
    
    :param self: 任务实例
    :param program_id: 程序ID编号
    :param code: 要执行的代码
    :param language: 代码语言，默认为Python
    :return: 执行结果
    """
    try:
        # 根据语言执行代码
        if language.lower() == 'python':
            # 直接执行Python代码，不创建临时文件
            import io
            import contextlib
            
            # 捕获标准输出和标准错误
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            returncode = 0
            try:
                # 使用contextlib重定向所有输出到StringIO对象
                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    # 定义用户代码执行环境
                    execution_env = {
                        'task_id': self.request.id,
                        'program_id': program_id,
                        'os': os,
                        'time': time
                    }
                     
                    # 记录开始时间
                    start_time = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 执行用户代码，传入执行环境
                    exec(code, execution_env)
                    
                    # 记录结束时间
                    end_time = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 打印任务完成信息，包含任务ID、开始时间和结束时间
                    print(f"=== 任务完成 === 任务ID: {self.request.id} 开始时间: {start_time} 结束时间: {end_time} ")
            except Exception as e:
                # 捕获执行过程中的异常
                returncode = 1
                # 将异常信息写入stderr
                stderr_capture.write(f"执行错误: {type(e).__name__}: {e}\n")
            
            # 获取捕获的输出
            stdout = stdout_capture.getvalue()
            stderr = stderr_capture.getvalue()
            
            output = {
                'program_id': program_id,
                'task_id': self.request.id,
                'returncode': returncode,
                'stdout': stdout,
                'stderr': stderr
            }
        else:
            output = {
                'program_id': program_id,
                'task_id': self.request.id,
                'returncode': 1,
                'stdout': '',
                'stderr': f'Unsupported language: {language}'
            }
        
        return output
    except Exception as e:
        return {
            'program_id': program_id,
            'task_id': self.request.id,
            'returncode': 1,
            'stdout': '',
            'stderr': str(e)
        }