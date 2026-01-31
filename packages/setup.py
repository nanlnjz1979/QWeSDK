from setuptools import setup, find_packages
import os

# 获取当前目录
here = os.path.abspath(os.path.dirname(__file__))

# 读取README.md文件
with open(os.path.join(here, 'README.md'), 'r', encoding='utf-8') as f:
    long_description = f.read()

# 读取requirements.txt文件
with open(os.path.join(here, 'requirements.txt'), 'r', encoding='utf-8') as f:
    install_requires = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='qwesdk',
    version='1.0.0',
    description='Quantitative SDK for Backtesting and Paper Trading',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/qwesdk',
    author='Your Name',
    author_email='your.email@example.com',
    license='MIT',
    packages=find_packages(),
    install_requires=install_requires,
    include_package_data=True,
    package_data={
        'm': ['*.json'],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Office/Business :: Financial :: Investment',
    ],
    python_requires='>=3.10',
    entry_points={
        'console_scripts': [
            'qwesdk-test=test_bigtrader:main',
        ],
    },
)