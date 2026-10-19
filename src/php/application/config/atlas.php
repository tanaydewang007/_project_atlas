<?php
defined('BASEPATH') OR exit('No direct script access allowed');

$config['atlas_api_url'] = rtrim(getenv('ATLAS_API_URL') ?: 'http://127.0.0.1:8000', '/');
$config['atlas_timeout'] = (int) (getenv('ATLAS_TIMEOUT') ?: 35);
$config['atlas_max_message'] = 1000;
$config['atlas_clients'] = array(
    'C-01' => array('name' => 'Northwind Utilities', 'key' => getenv('ATLAS_KEY_C01') ?: ''),
    'C-02' => array('name' => 'Blue Delta Infra', 'key' => getenv('ATLAS_KEY_C02') ?: ''),
);
