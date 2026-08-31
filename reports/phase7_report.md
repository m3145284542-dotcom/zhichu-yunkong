# Phase 7 — 多建筑泛化与多模型决策价值验证

Phase 7 固定选择 8 栋 office，在完全一致的 Phase 4.5/6 因果预测协议和按 Train 尺度归一化的 Phase 5 battery 下，对 Day-Week、LightGBM、XGBoost、CatBoost 同时评价预测与决策价值。Oracle 仅为不可部署 hindsight upper bound。

## 代表建筑（Train-only）

| building | mean_load | coefficient_of_variation | lag24_autocorrelation | lag168_autocorrelation | normalized_peak_valley_range | selection_reason |
| --- | --- | --- | --- | --- | --- | --- |
| Hog_office_Rolando | 299.2287 | 0.5610 | 0.9908 | 0.9731 | 2.6802 | Phase 3–6 canonical anchor; passed the same frozen quality rules |
| Hog_office_Lavon | 291.7353 | 1.5352 | 0.7162 | 0.3903 | 10.3134 | deterministic morphology coverage: high peak_to_average_ratio, high daily_profile_variability_normalized, high normalized_peak_valley_range |
| Hog_office_Joey | 1196.6396 | 0.4719 | 0.6124 | 0.4674 | 2.9353 | deterministic morphology coverage: high robust_outlier_fraction, low lag168_autocorrelation, high log_mean_load |
| Lamb_office_Caitlin | 22.1323 | 1.5660 | 0.7598 | 0.8614 | 7.0981 | deterministic morphology coverage: high daily_profile_variability_normalized, high robust_outlier_fraction, high coefficient_of_variation |
| Robin_office_Addie | 20.8344 | 0.3065 | 0.6379 | 0.5502 | 2.2162 | deterministic morphology coverage: low lag168_autocorrelation, low lag24_autocorrelation, low log_mean_load |
| Lamb_office_Gerardo | 8.7326 | 1.2357 | 0.7716 | 0.7950 | 7.3287 | deterministic morphology coverage: high daily_profile_variability_normalized, high peak_to_average_ratio, high normalized_peak_valley_range |
| Hog_office_Alexis | 19.3918 | 0.6994 | 0.6563 | 0.8312 | 3.5789 | deterministic morphology coverage: high weekday_weekend_difference_normalized, high daily_profile_variability_normalized, high peak_to_average_ratio |
| Hog_office_Byron | 954.2118 | 0.2053 | 0.7157 | 0.8759 | 1.6739 | deterministic morphology coverage: high log_mean_load, low daily_profile_variability_normalized, low coefficient_of_variation |

## Validation 模型选择

| building | model_family | candidate | best_iteration | validation_MAE | validation_mean_daily_peak | validation_mean_regret_vs_oracle |
| --- | --- | --- | --- | --- | --- | --- |
| Hog_office_Rolando | DayWeek | Phase6_frozen_w0.5 | 0 | 9.4030 | 460.0669 | 18.8716 |
| Hog_office_Rolando | LightGBM | balanced | 296 | 7.7105 | 458.4885 | 17.2932 |
| Hog_office_Rolando | XGBoost | balanced | 190 | 7.7919 | 459.2375 | 18.0422 |
| Hog_office_Rolando | CatBoost | balanced | 143 | 8.8390 | 459.7311 | 18.5358 |
| Hog_office_Lavon | DayWeek | Phase6_frozen_w0.5 | 0 | 1.2690 | 19.2463 | 3.7795 |
| Hog_office_Lavon | LightGBM | balanced | 173 | 7.0586 | 19.8532 | 4.3864 |
| Hog_office_Lavon | XGBoost | balanced | 195 | 6.4823 | 21.8892 | 6.4224 |
| Hog_office_Lavon | CatBoost | balanced | 283 | 8.6325 | 26.2609 | 10.7942 |
| Hog_office_Joey | DayWeek | Phase6_frozen_w0.5 | 0 | 69.5403 | 1330.8943 | 95.5631 |
| Hog_office_Joey | LightGBM | balanced | 156 | 64.7232 | 1342.0012 | 106.6700 |
| Hog_office_Joey | XGBoost | small_regularized | 149 | 68.2630 | 1348.1003 | 112.7692 |
| Hog_office_Joey | CatBoost | balanced | 254 | 59.1911 | 1338.3122 | 102.9810 |
| Lamb_office_Caitlin | DayWeek | Phase6_frozen_w0.5 | 0 | 10.5719 | 90.8013 | 6.5919 |
| Lamb_office_Caitlin | LightGBM | small_regularized | 112 | 12.3709 | 89.9273 | 5.7178 |
| Lamb_office_Caitlin | XGBoost | small_regularized | 151 | 9.7999 | 89.7505 | 5.5410 |
| Lamb_office_Caitlin | CatBoost | small_regularized | 139 | 11.7153 | 89.6685 | 5.4590 |
| Robin_office_Addie | DayWeek | Phase6_frozen_w0.5 | 0 | 3.0525 | 25.1798 | 4.0328 |
| Robin_office_Addie | LightGBM | balanced | 199 | 2.1612 | 24.5424 | 3.3954 |
| Robin_office_Addie | XGBoost | balanced | 91 | 2.2292 | 24.6026 | 3.4556 |
| Robin_office_Addie | CatBoost | balanced | 207 | 2.2241 | 24.6564 | 3.5094 |
| Lamb_office_Gerardo | DayWeek | Phase6_frozen_w0.5 | 0 | 1.6810 | 4.6518 | 0.2516 |
| Lamb_office_Gerardo | LightGBM | balanced | 119 | 1.9884 | 4.5867 | 0.1865 |
| Lamb_office_Gerardo | XGBoost | small_regularized | 163 | 2.2333 | 4.8420 | 0.4418 |
| Lamb_office_Gerardo | CatBoost | balanced | 130 | 2.0106 | 4.7204 | 0.3201 |
| Hog_office_Alexis | DayWeek | Phase6_frozen_w0.5 | 0 | 3.1920 | 27.5075 | 3.6156 |
| Hog_office_Alexis | LightGBM | small_regularized | 68 | 3.2456 | 27.1330 | 3.2411 |
| Hog_office_Alexis | XGBoost | balanced | 84 | 3.1210 | 27.0615 | 3.1697 |
| Hog_office_Alexis | CatBoost | balanced | 64 | 3.4669 | 27.0754 | 3.1836 |
| Hog_office_Byron | DayWeek | Phase6_frozen_w0.5 | 0 | 46.5762 | 1035.8257 | 74.1806 |
| Hog_office_Byron | LightGBM | balanced | 414 | 21.8434 | 1016.9232 | 55.2780 |
| Hog_office_Byron | XGBoost | balanced | 499 | 22.6206 | 1019.0533 | 57.4082 |
| Hog_office_Byron | CatBoost | balanced | 498 | 25.5706 | 1022.7001 | 61.0550 |

## Test forecast metrics

| building | method | normalized_MAE | normalized_RMSE | peak_quartile_MAE | bias | daily_peak_hour_MAE | daily_peak_hour_exact_rate | daily_top3_overlap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hog_office_Rolando | DayWeek | 0.0290 | 0.0410 | 7.2869 | 4.6896 | 1.5333 | 0.3000 | 0.5778 |
| Hog_office_Rolando | LightGBM | 0.0379 | 0.0568 | 5.8331 | 8.6892 | 3.6000 | 0.2333 | 0.5222 |
| Hog_office_Rolando | XGBoost | 0.0271 | 0.0393 | 5.5909 | 4.9425 | 2.7333 | 0.2000 | 0.5000 |
| Hog_office_Rolando | CatBoost | 0.0308 | 0.0428 | 6.2515 | 6.0469 | 1.7667 | 0.2667 | 0.5556 |
| Hog_office_Lavon | DayWeek | 0.0078 | 0.0101 | 2.2565 | -0.0576 | 8.8333 | 0.0667 | 0.3222 |
| Hog_office_Lavon | LightGBM | 0.0426 | 0.0511 | 6.0664 | 12.6739 | 8.4000 | 0.0333 | 0.0889 |
| Hog_office_Lavon | XGBoost | 0.0434 | 0.0557 | 6.2154 | 12.8631 | 7.5667 | 0.0333 | 0.1000 |
| Hog_office_Lavon | CatBoost | 0.0480 | 0.0816 | 12.8277 | 9.7204 | 7.4667 | 0.0333 | 0.0222 |
| Hog_office_Joey | DayWeek | 0.0611 | 0.0909 | 108.3279 | -38.3838 | 1.9667 | 0.2000 | 0.4000 |
| Hog_office_Joey | LightGBM | 0.0629 | 0.0879 | 105.2835 | -53.0339 | 2.1000 | 0.2333 | 0.4667 |
| Hog_office_Joey | XGBoost | 0.0641 | 0.0884 | 106.3757 | -54.0006 | 2.3333 | 0.2667 | 0.3778 |
| Hog_office_Joey | CatBoost | 0.0646 | 0.0898 | 103.2345 | -52.0095 | 2.7000 | 0.2333 | 0.3889 |
| Lamb_office_Caitlin | DayWeek | 0.5569 | 0.8766 | 16.1233 | 3.6529 | 2.1000 | 0.3333 | 0.6111 |
| Lamb_office_Caitlin | LightGBM | 0.4282 | 0.6410 | 17.1021 | -3.1410 | 2.5333 | 0.2333 | 0.5556 |
| Lamb_office_Caitlin | XGBoost | 0.4167 | 0.5967 | 15.5668 | -1.7699 | 2.3667 | 0.2667 | 0.5556 |
| Lamb_office_Caitlin | CatBoost | 0.5549 | 0.7230 | 17.4336 | -5.4923 | 1.9333 | 0.2667 | 0.6000 |
| Robin_office_Addie | DayWeek | 0.1258 | 0.1618 | 2.3994 | 0.5824 | 4.4000 | 0.1000 | 0.3000 |
| Robin_office_Addie | LightGBM | 0.1357 | 0.1829 | 1.7032 | 1.8371 | 5.5000 | 0.1000 | 0.2778 |
| Robin_office_Addie | XGBoost | 0.1485 | 0.1936 | 1.8180 | 2.2728 | 4.7667 | 0.0333 | 0.2778 |
| Robin_office_Addie | CatBoost | 0.1359 | 0.1821 | 1.4102 | 1.7353 | 5.7333 | 0.0000 | 0.2889 |
| Lamb_office_Gerardo | DayWeek | 0.5215 | 0.9066 | 7.3322 | 0.9904 | 2.8000 | 0.3000 | 0.4889 |
| Lamb_office_Gerardo | LightGBM | 0.3364 | 0.4964 | 4.3798 | 1.2167 | 2.6667 | 0.3667 | 0.5000 |
| Lamb_office_Gerardo | XGBoost | 0.3590 | 0.5404 | 4.4816 | 1.1568 | 2.8000 | 0.3667 | 0.5000 |
| Lamb_office_Gerardo | CatBoost | 0.4092 | 0.5750 | 5.1073 | 1.1880 | 2.1667 | 0.3333 | 0.4778 |
| Hog_office_Alexis | DayWeek | 0.1273 | 0.2216 | 4.0104 | -0.0943 | 4.8667 | 0.1667 | 0.4333 |
| Hog_office_Alexis | LightGBM | 0.1070 | 0.1729 | 3.8352 | -0.7132 | 4.9333 | 0.1000 | 0.3778 |
| Hog_office_Alexis | XGBoost | 0.1126 | 0.1760 | 3.9311 | -0.8172 | 4.0667 | 0.1667 | 0.4111 |
| Hog_office_Alexis | CatBoost | 0.1200 | 0.1774 | 3.8579 | -0.8696 | 3.4000 | 0.1667 | 0.4333 |
| Hog_office_Byron | DayWeek | 0.0383 | 0.0643 | 54.1218 | 5.5941 | 1.0667 | 0.2667 | 0.6556 |
| Hog_office_Byron | LightGBM | 0.0279 | 0.0465 | 22.1364 | -4.3813 | 1.5667 | 0.3667 | 0.6000 |
| Hog_office_Byron | XGBoost | 0.0268 | 0.0439 | 23.1641 | -2.3287 | 2.2000 | 0.1667 | 0.5778 |
| Hog_office_Byron | CatBoost | 0.0254 | 0.0421 | 24.0886 | -2.3177 | 1.6667 | 0.1333 | 0.5667 |

## Test decision metrics

| building | method | mean_daily_peak | worst_10pct_daily_peak | mean_regret_vs_oracle | p90_regret | max_regret | oracle_capture_ratio | equivalent_full_cycles |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hog_office_Rolando | DayWeek | 431.6004 | 452.6436 | 11.4286 | 18.4220 | 32.1724 | 0.2040 | 6.8263 |
| Hog_office_Rolando | LightGBM | 431.2992 | 453.0817 | 11.1274 | 17.0718 | 28.5901 | 0.1809 | 5.6642 |
| Hog_office_Rolando | XGBoost | 431.2409 | 452.1858 | 11.0691 | 15.6618 | 28.2463 | 0.1560 | 5.8817 |
| Hog_office_Rolando | CatBoost | 431.6296 | 453.9681 | 11.4578 | 16.2652 | 27.7592 | 0.1769 | 5.6819 |
| Hog_office_Lavon | DayWeek | 15.6511 | 18.5684 | 3.5934 | 6.1639 | 7.4828 | -0.1264 | 0.6124 |
| Hog_office_Lavon | LightGBM | 17.6224 | 23.8037 | 5.5646 | 8.3919 | 12.8696 | -0.7476 | 1.2618 |
| Hog_office_Lavon | XGBoost | 19.2760 | 24.8392 | 7.2183 | 12.0572 | 13.4770 | -1.3124 | 1.9845 |
| Hog_office_Lavon | CatBoost | 27.4703 | 62.3199 | 15.4125 | 45.1619 | 52.0187 | -4.0921 | 4.1148 |
| Hog_office_Joey | DayWeek | 1333.2124 | 1503.7175 | 83.8405 | 166.4973 | 195.9523 | 0.2420 | 8.6030 |
| Hog_office_Joey | LightGBM | 1334.8763 | 1498.1988 | 85.5044 | 161.7041 | 197.6282 | 0.2274 | 8.5640 |
| Hog_office_Joey | XGBoost | 1340.1482 | 1515.9292 | 90.7763 | 184.8898 | 212.6183 | 0.1705 | 8.6947 |
| Hog_office_Joey | CatBoost | 1330.5202 | 1493.3629 | 81.1483 | 166.2050 | 184.0729 | 0.2589 | 8.6603 |
| Lamb_office_Caitlin | DayWeek | 95.2191 | 152.6644 | 5.8963 | 13.2824 | 16.3975 | -0.9710 | 18.4321 |
| Lamb_office_Caitlin | LightGBM | 94.8025 | 154.6963 | 5.4797 | 7.7940 | 10.8396 | -0.5238 | 19.1126 |
| Lamb_office_Caitlin | XGBoost | 95.5502 | 155.0569 | 6.2274 | 11.1248 | 12.7217 | -0.9851 | 21.4810 |
| Lamb_office_Caitlin | CatBoost | 95.0890 | 154.4307 | 5.7663 | 8.2904 | 12.8966 | -0.8671 | 20.2001 |
| Robin_office_Addie | DayWeek | 18.7314 | 24.9877 | 3.7530 | 6.8358 | 7.4123 | -1.9398 | 14.1003 |
| Robin_office_Addie | LightGBM | 17.5099 | 23.8613 | 2.5315 | 4.4884 | 5.7845 | -0.7487 | 10.7966 |
| Robin_office_Addie | XGBoost | 17.2623 | 23.1732 | 2.2838 | 3.5558 | 4.8643 | -0.3787 | 9.9734 |
| Robin_office_Addie | CatBoost | 17.4983 | 23.4341 | 2.5198 | 4.2822 | 5.3085 | -0.5985 | 10.3498 |
| Lamb_office_Gerardo | DayWeek | 26.3364 | 50.4136 | 3.1305 | 5.6307 | 7.3800 | -0.6222 | 15.0410 |
| Lamb_office_Gerardo | LightGBM | 25.4371 | 49.8010 | 2.2312 | 4.5249 | 7.1312 | -0.0554 | 14.1037 |
| Lamb_office_Gerardo | XGBoost | 25.2547 | 49.7131 | 2.0489 | 4.4260 | 5.9435 | -0.0792 | 16.8185 |
| Lamb_office_Gerardo | CatBoost | 25.2541 | 49.3361 | 2.0482 | 3.9004 | 5.9435 | -0.2004 | 18.1256 |
| Hog_office_Alexis | DayWeek | 26.1864 | 36.5275 | 2.9958 | 6.3843 | 10.7412 | -0.6875 | 18.0011 |
| Hog_office_Alexis | LightGBM | 25.6642 | 35.1319 | 2.4736 | 4.6584 | 8.3931 | -0.2219 | 17.2402 |
| Hog_office_Alexis | XGBoost | 25.6531 | 34.6294 | 2.4625 | 5.0465 | 9.0930 | -0.2493 | 16.3812 |
| Hog_office_Alexis | CatBoost | 25.5946 | 34.9902 | 2.4040 | 4.6490 | 7.3294 | -0.1828 | 17.1019 |
| Hog_office_Byron | DayWeek | 989.5412 | 1124.8759 | 47.1232 | 86.6844 | 115.4569 | 0.3264 | 14.8141 |
| Hog_office_Byron | LightGBM | 977.9092 | 1113.4791 | 35.4912 | 56.5748 | 144.1389 | 0.5705 | 13.7509 |
| Hog_office_Byron | XGBoost | 978.3151 | 1119.5084 | 35.8972 | 70.3009 | 116.7731 | 0.5578 | 13.8477 |
| Hog_office_Byron | CatBoost | 980.4142 | 1116.0155 | 37.9963 | 68.7951 | 149.8811 | 0.5521 | 13.7851 |

## Cross-building stability

| method | average_normalized_MAE | median_normalized_MAE | std_normalized_MAE | forecast_average_rank | forecast_median_rank | forecast_win_count | average_normalized_peak_quartile_MAE | std_normalized_peak_quartile_MAE | peak_average_rank | peak_win_count | average_normalized_mean_regret | median_normalized_mean_regret | std_normalized_mean_regret | decision_average_rank | decision_median_rank | decision_win_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DayWeek | 0.1835 | 0.0934 | 0.2094 | 2.6250 | 3.0000 | 3 | 0.2637 | 0.3184 | 3.3750 | 1 | 0.1430 | 0.1126 | 0.1177 | 3.1250 | 3.5000 | 1 |
| LightGBM | 0.1473 | 0.0850 | 0.1417 | 2.1250 | 2.0000 | 2 | 0.2174 | 0.2676 | 1.7500 | 3 | 0.1161 | 0.0964 | 0.0898 | 2.2500 | 2.5000 | 2 |
| XGBoost | 0.1498 | 0.0884 | 0.1437 | 2.2500 | 2.0000 | 2 | 0.2114 | 0.2500 | 2.2500 | 2 | 0.1175 | 0.0927 | 0.0923 | 2.3750 | 2.0000 | 2 |
| CatBoost | 0.1736 | 0.0923 | 0.1855 | 3.0000 | 3.0000 | 1 | 0.2314 | 0.2832 | 2.6250 | 2 | 0.1187 | 0.0943 | 0.0843 | 2.2500 | 2.0000 | 3 |

Forecast rank 与 decision rank 的逐建筑逐方法完全一致率为 0.344；因此两类排序不能被默认视为等价。

## 核心研究问题结论

- Q1：传统 Forecast 最优方法并不稳定一致；8 栋中 DayWeek/LightGBM/XGBoost/CatBoost 的 normalized-MAE win count 分别为 3/2/2/1。仅比较三种树模型时，LightGBM 的跨建筑 average forecast rank 最低（2.125）。
- Q2：Forecast winner 仅在 2/8 栋同时是 battery decision winner；不能用预测冠军替代决策冠军。
- Q3：Phase 5–6 所见的 forecast-to-decision 不完全一致具有跨建筑证据：top winner 在 6/8 栋不一致，全部 building×method 的精确 rank 一致率仅 0.344。
- Q4：LightGBM 的平均 normalized MAE（0.1473）、peak-region average rank（1.750）和平均 normalized regret（0.1161）均为三树模型最佳或并列最佳；但 decision average rank 与 CatBoost 同为 2.250，CatBoost 有更多 decision wins 且 decision variability 更低。不存在所有维度、所有建筑的单一支配模型。

## Paired comparison

| row_scope | building | model_a | model_b | mean_daily_peak_difference_a_minus_b | median_daily_peak_difference_a_minus_b | mean_normalized_daily_peak_difference | daily_a_better | daily_equal | daily_a_worse | normalized_MAE_difference_a_minus_b | normalized_regret_difference_a_minus_b | across_building_a_better | across_building_equal | across_building_a_worse | median_normalized_improvement_a_vs_b | mean_normalized_improvement_a_vs_b |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| building | Hog_office_Alexis | DayWeek | LightGBM | 0.5222 | 0.4139 | 0.0270 | 11 | 0 | 19 | 0.0203 | 0.0270 | nan | nan | nan | nan | nan |
| building | Hog_office_Alexis | DayWeek | XGBoost | 0.5333 | 0.5677 | 0.0276 | 12 | 0 | 18 | 0.0147 | 0.0276 | nan | nan | nan | nan | nan |
| building | Hog_office_Alexis | DayWeek | CatBoost | 0.5918 | 0.2270 | 0.0306 | 14 | 0 | 16 | 0.0073 | 0.0306 | nan | nan | nan | nan | nan |
| building | Hog_office_Alexis | LightGBM | XGBoost | 0.0111 | 0.0354 | 0.0006 | 14 | 0 | 16 | -0.0056 | 0.0006 | nan | nan | nan | nan | nan |
| building | Hog_office_Alexis | LightGBM | CatBoost | 0.0696 | -0.0180 | 0.0036 | 15 | 0 | 15 | -0.0130 | 0.0036 | nan | nan | nan | nan | nan |
| building | Hog_office_Alexis | XGBoost | CatBoost | 0.0585 | -0.0145 | 0.0030 | 16 | 0 | 14 | -0.0074 | 0.0030 | nan | nan | nan | nan | nan |
| building | Hog_office_Byron | DayWeek | LightGBM | 11.6320 | 5.8864 | 0.0122 | 12 | 0 | 18 | 0.0104 | 0.0122 | nan | nan | nan | nan | nan |
| building | Hog_office_Byron | DayWeek | XGBoost | 11.2260 | 8.5572 | 0.0118 | 9 | 0 | 21 | 0.0116 | 0.0118 | nan | nan | nan | nan | nan |
| building | Hog_office_Byron | DayWeek | CatBoost | 9.1269 | 5.4053 | 0.0096 | 13 | 0 | 17 | 0.0129 | 0.0096 | nan | nan | nan | nan | nan |
| building | Hog_office_Byron | LightGBM | XGBoost | -0.4059 | -0.1095 | -0.0004 | 16 | 0 | 14 | 0.0011 | -0.0004 | nan | nan | nan | nan | nan |
| building | Hog_office_Byron | LightGBM | CatBoost | -2.5051 | -1.9573 | -0.0026 | 18 | 0 | 12 | 0.0025 | -0.0026 | nan | nan | nan | nan | nan |
| building | Hog_office_Byron | XGBoost | CatBoost | -2.0991 | 0.4327 | -0.0022 | 15 | 0 | 15 | 0.0014 | -0.0022 | nan | nan | nan | nan | nan |
| building | Hog_office_Joey | DayWeek | LightGBM | -1.6639 | -8.9243 | -0.0014 | 20 | 0 | 10 | -0.0018 | -0.0014 | nan | nan | nan | nan | nan |
| building | Hog_office_Joey | DayWeek | XGBoost | -6.9358 | -17.0252 | -0.0058 | 22 | 0 | 8 | -0.0030 | -0.0058 | nan | nan | nan | nan | nan |
| building | Hog_office_Joey | DayWeek | CatBoost | 2.6922 | -5.0208 | 0.0023 | 16 | 0 | 14 | -0.0035 | 0.0023 | nan | nan | nan | nan | nan |
| building | Hog_office_Joey | LightGBM | XGBoost | -5.2719 | -4.6065 | -0.0044 | 19 | 0 | 11 | -0.0012 | -0.0044 | nan | nan | nan | nan | nan |
| building | Hog_office_Joey | LightGBM | CatBoost | 4.3562 | 3.2788 | 0.0037 | 12 | 0 | 18 | -0.0017 | 0.0037 | nan | nan | nan | nan | nan |
| building | Hog_office_Joey | XGBoost | CatBoost | 9.6281 | 11.6974 | 0.0081 | 6 | 0 | 24 | -0.0005 | 0.0081 | nan | nan | nan | nan | nan |
| building | Hog_office_Lavon | DayWeek | LightGBM | -1.9713 | -1.6024 | -0.0066 | 23 | 0 | 7 | -0.0348 | -0.0066 | nan | nan | nan | nan | nan |
| building | Hog_office_Lavon | DayWeek | XGBoost | -3.6249 | -2.9746 | -0.0122 | 30 | 0 | 0 | -0.0356 | -0.0122 | nan | nan | nan | nan | nan |
| building | Hog_office_Lavon | DayWeek | CatBoost | -11.8192 | -7.1481 | -0.0397 | 30 | 0 | 0 | -0.0402 | -0.0397 | nan | nan | nan | nan | nan |
| building | Hog_office_Lavon | LightGBM | XGBoost | -1.6536 | -1.6261 | -0.0056 | 24 | 0 | 6 | -0.0008 | -0.0056 | nan | nan | nan | nan | nan |
| building | Hog_office_Lavon | LightGBM | CatBoost | -9.8479 | -5.4785 | -0.0331 | 28 | 0 | 2 | -0.0054 | -0.0331 | nan | nan | nan | nan | nan |
| building | Hog_office_Lavon | XGBoost | CatBoost | -8.1943 | -3.4092 | -0.0275 | 26 | 0 | 4 | -0.0045 | -0.0275 | nan | nan | nan | nan | nan |
| building | Hog_office_Rolando | DayWeek | LightGBM | 0.3013 | -0.0237 | 0.0010 | 15 | 0 | 15 | -0.0089 | 0.0010 | nan | nan | nan | nan | nan |
| building | Hog_office_Rolando | DayWeek | XGBoost | 0.3595 | -0.2697 | 0.0012 | 15 | 0 | 15 | 0.0019 | 0.0012 | nan | nan | nan | nan | nan |
| building | Hog_office_Rolando | DayWeek | CatBoost | -0.0292 | 0.4853 | -0.0001 | 13 | 0 | 17 | -0.0018 | -0.0001 | nan | nan | nan | nan | nan |
| building | Hog_office_Rolando | LightGBM | XGBoost | 0.0583 | 0.1977 | 0.0002 | 11 | 0 | 19 | 0.0108 | 0.0002 | nan | nan | nan | nan | nan |
| building | Hog_office_Rolando | LightGBM | CatBoost | -0.3304 | 0.1065 | -0.0011 | 12 | 0 | 18 | 0.0071 | -0.0011 | nan | nan | nan | nan | nan |
| building | Hog_office_Rolando | XGBoost | CatBoost | -0.3887 | -0.6952 | -0.0013 | 17 | 0 | 13 | -0.0037 | -0.0013 | nan | nan | nan | nan | nan |
| building | Lamb_office_Caitlin | DayWeek | LightGBM | 0.4166 | 0.4891 | 0.0194 | 13 | 1 | 16 | 0.1287 | 0.0194 | nan | nan | nan | nan | nan |
| building | Lamb_office_Caitlin | DayWeek | XGBoost | -0.3311 | 0.1320 | -0.0154 | 14 | 1 | 15 | 0.1402 | -0.0154 | nan | nan | nan | nan | nan |
| building | Lamb_office_Caitlin | DayWeek | CatBoost | 0.1301 | -0.6767 | 0.0061 | 17 | 0 | 13 | 0.0020 | 0.0061 | nan | nan | nan | nan | nan |
| building | Lamb_office_Caitlin | LightGBM | XGBoost | -0.7477 | -0.2813 | -0.0348 | 18 | 0 | 12 | 0.0115 | -0.0348 | nan | nan | nan | nan | nan |
| building | Lamb_office_Caitlin | LightGBM | CatBoost | -0.2865 | -0.0896 | -0.0133 | 16 | 0 | 14 | -0.1268 | -0.0133 | nan | nan | nan | nan | nan |
| building | Lamb_office_Caitlin | XGBoost | CatBoost | 0.4612 | 0.1084 | 0.0215 | 12 | 1 | 17 | -0.1383 | 0.0215 | nan | nan | nan | nan | nan |
| building | Lamb_office_Gerardo | DayWeek | LightGBM | 0.8992 | 0.0000 | 0.1052 | 14 | 3 | 13 | 0.1852 | 0.1052 | nan | nan | nan | nan | nan |
| building | Lamb_office_Gerardo | DayWeek | XGBoost | 1.0816 | 0.0490 | 0.1266 | 12 | 3 | 15 | 0.1625 | 0.1266 | nan | nan | nan | nan | nan |
| building | Lamb_office_Gerardo | DayWeek | CatBoost | 1.0823 | 0.6149 | 0.1267 | 11 | 1 | 18 | 0.1123 | 0.1267 | nan | nan | nan | nan | nan |
| building | Lamb_office_Gerardo | LightGBM | XGBoost | 0.1824 | 0.0000 | 0.0213 | 13 | 3 | 14 | -0.0227 | 0.0213 | nan | nan | nan | nan | nan |
| building | Lamb_office_Gerardo | LightGBM | CatBoost | 0.1831 | -0.0663 | 0.0214 | 16 | 1 | 13 | -0.0728 | 0.0214 | nan | nan | nan | nan | nan |
| building | Lamb_office_Gerardo | XGBoost | CatBoost | 0.0007 | 0.0000 | 0.0001 | 14 | 2 | 14 | -0.0502 | 0.0001 | nan | nan | nan | nan | nan |
| building | Robin_office_Addie | DayWeek | LightGBM | 1.2215 | 0.9396 | 0.0584 | 4 | 0 | 26 | -0.0100 | 0.0584 | nan | nan | nan | nan | nan |
| building | Robin_office_Addie | DayWeek | XGBoost | 1.4692 | 1.1694 | 0.0702 | 5 | 0 | 25 | -0.0227 | 0.0702 | nan | nan | nan | nan | nan |
| building | Robin_office_Addie | DayWeek | CatBoost | 1.2332 | 1.1876 | 0.0589 | 5 | 0 | 25 | -0.0101 | 0.0589 | nan | nan | nan | nan | nan |
| building | Robin_office_Addie | LightGBM | XGBoost | 0.2477 | 0.1127 | 0.0118 | 8 | 0 | 22 | -0.0127 | 0.0118 | nan | nan | nan | nan | nan |
| building | Robin_office_Addie | LightGBM | CatBoost | 0.0116 | -0.0311 | 0.0006 | 16 | 0 | 14 | -0.0001 | 0.0006 | nan | nan | nan | nan | nan |
| building | Robin_office_Addie | XGBoost | CatBoost | -0.2360 | -0.1918 | -0.0113 | 20 | 0 | 10 | 0.0126 | -0.0113 | nan | nan | nan | nan | nan |
| across_building | __all__ | DayWeek | LightGBM | 1.4197 | 0.2069 | 0.0269 | 112 | 4 | 124 | 0.0361 | 0.0269 | 2.0000 | 0.0000 | 6.0000 | -0.0158 | -0.0269 |
| across_building | __all__ | DayWeek | XGBoost | 0.4722 | 0.0905 | 0.0255 | 119 | 4 | 117 | 0.0337 | 0.0255 | 3.0000 | 0.0000 | 5.0000 | -0.0065 | -0.0255 |
| across_building | __all__ | DayWeek | CatBoost | 0.3760 | 0.3562 | 0.0243 | 119 | 1 | 120 | 0.0099 | 0.0243 | 2.0000 | 0.0000 | 6.0000 | -0.0078 | -0.0243 |
| across_building | __all__ | LightGBM | XGBoost | -0.9475 | -0.0547 | -0.0014 | 123 | 3 | 114 | -0.0024 | -0.0014 | 4.0000 | 0.0000 | 4.0000 | 0.0001 | 0.0014 |
| across_building | __all__ | LightGBM | CatBoost | -1.0437 | -0.0487 | -0.0026 | 133 | 1 | 106 | -0.0263 | -0.0026 | 4.0000 | 0.0000 | 4.0000 | 0.0003 | 0.0026 |
| across_building | __all__ | XGBoost | CatBoost | -0.0962 | -0.0073 | -0.0012 | 126 | 3 | 111 | -0.0238 | -0.0012 | 4.0000 | 0.0000 | 4.0000 | 0.0006 | 0.0012 |

## Ensemble

Ensemble 未表现出满足预注册 stop rule 的稳定 Validation 泛化收益，已停止且未读取 Test 来修改 alpha。

## Audits

Hog Phase 6 reproduction: {'building': 'Hog_office_Rolando', 'protocol': 'Phase 4.5 canonical / Phase 6 reproduction', 'test_prediction_max_absolute_delta': 5.684341886080802e-14, 'mean_daily_peak_absolute_delta_vs_phase6': 0.0, 'tolerance': 1e-06, 'passed': True}

Constraint: PASS; Leakage: PASS。所有 Phase 3–6 tracked artifact hashes 在运行前后相同。

## 结论边界

结论仅适用于这些 Train-only 规则选出的 office、固定 2017-11 Validation/2017-12 Test、24h horizon、daily-reset battery。Test 只用于冻结后的评价；未使用天气、MPC、RL、CVaR/robust、深度学习或 Test 后调参。
