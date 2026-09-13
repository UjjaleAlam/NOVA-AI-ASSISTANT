import core.data_science_agent as ds
import numpy as np

print('=== DATA SCIENCE AGENT FULL TEST ===')

# 1. Create dataset from synthetic data
np.random.seed(42)
n = 1000
data = {
    'age': np.random.normal(40, 15, n).astype(int).clip(18, 80),
    'income': np.random.lognormal(10.5, 0.5, n),
    'education_years': np.random.normal(14, 3, n).astype(int).clip(0, 25),
    'experience': np.random.normal(15, 10, n).astype(int).clip(0, 50),
    'department': np.random.choice(['Engineering', 'Sales', 'Marketing', 'HR', 'Finance'], n),
    'performance_score': np.random.normal(75, 15, n).clip(0, 100),
    'satisfaction': np.random.choice(['Low', 'Medium', 'High'], n, p=[0.2, 0.5, 0.3]),
    'left_company': np.random.choice([0, 1], n, p=[0.85, 0.15])
}

ds_id = ds.create_dataset_from_dict(data, 'Employee Data', 'Synthetic HR dataset for testing')
print('1. Dataset created: ' + ds_id)

# 2. List datasets
datasets = ds.list_datasets()
print('2. Datasets: ' + str(len(datasets)))

# 3. Get dataset info
info = ds.get_dataset(ds_id)
print('3. Dataset info: ' + info['name'] + ', rows=' + str(info['rows']) + ', cols=' + str(info['columns']))

# 4. Run EDA
eda = ds.run_eda(ds_id)
missing_count = sum(1 for v in eda['missing_values'].values() if v > 0)
print('4. EDA completed: shape=' + str(eda['shape']) + ', missing=' + str(missing_count) + ' cols')

# 5. Correlation analysis
corr = ds.correlation_analysis(ds_id, target='income')
print('5. Correlation analysis: ' + str(len(corr.get('high_correlations', []))) + ' high correlations')

# 6. Statistical tests
ttest = ds.t_test_1sample(ds_id, 'age', 40)
print('6. T-test (age vs 40): t=' + str(round(ttest['t_statistic'], 3)) + ', p=' + str(round(ttest['p_value'], 4)))

ttest2 = ds.t_test_2sample(ds_id, 'income', 'department', 'Engineering', 'Sales')
print('   T-test (income Eng vs Sales): t=' + str(round(ttest2['t_statistic'], 3)) + ', p=' + str(round(ttest2['p_value'], 4)))

chi2 = ds.chi2_test(ds_id, 'department', 'satisfaction')
print('   Chi2 (dept vs satisfaction): chi2=' + str(round(chi2['chi2_statistic'], 3)) + ', p=' + str(round(chi2['p_value'], 4)))

anova = ds.anova_test(ds_id, 'income', 'department')
print('   ANOVA (income by dept): F=' + str(round(anova['f_statistic'], 3)) + ', p=' + str(round(anova['p_value'], 4)))

mw = ds.mannwhitney_test(ds_id, 'income', 'left_company', 0, 1)
print('   Mann-Whitney (income by left): U=' + str(round(mw['u_statistic'], 1)) + ', p=' + str(round(mw['p_value'], 4)))

norm = ds.normality_test(ds_id, 'income')
print('   Normality (income): ' + norm['conclusion'] + ' (p=' + str(round(norm['p_value'], 4)) + ')')

# 7. Visualizations
hist = ds.create_histogram(ds_id, 'income', bins=30, kde=True)
print('7. Histogram: ' + hist['figure_path'])

scatter = ds.create_scatter(ds_id, 'experience', 'income', color_col='department')
print('   Scatter: ' + scatter['figure_path'])

box = ds.create_boxplot(ds_id, 'income', 'department')
print('   Box plot: ' + box['figure_path'])

heatmap = ds.create_correlation_heatmap(ds_id)
print('   Heatmap: ' + heatmap['figure_path'])

line = ds.create_lineplot(ds_id, 'age', ['income', 'performance_score'])
print('   Line plot: ' + line['figure_path'])

bar = ds.create_barplot(ds_id, 'department', 'income', aggfunc='mean')
print('   Bar plot: ' + bar['figure_path'])

# 8. ML - Regression
reg = ds.train_regression(ds_id, 'income', ['age', 'education_years', 'experience'], 'random_forest')
print('8. Regression model: ' + reg['model_id'] + ', test R2=' + str(round(reg['metrics']['test_r2'], 3)))

# 9. ML - Classification
clf = ds.train_classification(ds_id, 'left_company', ['age', 'income', 'education_years', 'experience', 'performance_score'], 'random_forest')
print('9. Classification model: ' + clf['model_id'] + ', test acc=' + str(round(clf['metrics']['test_accuracy'], 3)))

# 10. ML - Clustering
clust = ds.train_clustering(ds_id, ['age', 'income', 'education_years', 'experience'], n_clusters=3)
print('10. Clustering: ' + clust['model_id'] + ', inertia=' + str(round(clust['inertia'], 1)))

# 11. Predictions
pred = ds.predict(reg['model_id'], {'age': 35, 'education_years': 16, 'experience': 10})
print('11. Regression prediction: income=$' + str(int(pred['prediction'])))

pred2 = ds.predict(clf['model_id'], {'age': 35, 'income': 80000, 'education_years': 16, 'experience': 10, 'performance_score': 80})
print('    Classification prediction: left=' + str(pred2['prediction_label']) + ' (conf=' + str(round(pred2['confidence'], 2)) + ')')

# 12. Workflow
wf_id = ds.create_workflow('HR Analysis', [
    {'type': 'eda', 'dataset_id': ds_id},
    {'type': 'train_model', 'model_type': 'regression', 'dataset_id': ds_id, 
     'target': 'income', 'features': ['age', 'education_years', 'experience']},
    {'type': 'train_model', 'model_type': 'classification', 'dataset_id': ds_id,
     'target': 'left_company', 'features': ['age', 'income', 'education_years', 'experience']}
], dataset_ids=[ds_id])
print('12. Workflow created: ' + wf_id)

wf_result = ds.run_workflow(wf_id)
print('    Workflow run: ' + str(len(wf_result['steps'])) + ' steps completed')

print()
print('=== ALL TESTS PASSED ===')