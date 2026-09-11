"""Additional multivariate analysis engines.

Each class uses the same result contract as the core engines.  The functions
are intentionally conservative: unsuitable selections return clear failed
preconditions instead of attempting a calculation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cross_decomposition import CCA, PLSRegression
from sklearn.decomposition import FactorAnalysis, FastICA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis
from sklearn.manifold import MDS
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import cross_val_predict
from sklearn.preprocessing import StandardScaler

from ..core.assumptions import AssumptionResult, PreconditionCheck, summarize_assumptions, bartlett_sphericity, kmo_test
from ..utils import AnalysisResult, _to_jsonable
from .base import BaseAnalysis


def _result(obj, config, variables):
    r = AnalysisResult(obj.name, obj._purpose, obj.category, obj._formula)
    r.user_config, r.data_used = config, {"variables": list(variables)}
    return r


def _matrix(df, cols): return df[list(cols)].apply(pd.to_numeric, errors="coerce")


def _fail(r, text):
    r.applicable = False; r.preconditions = [PreconditionCheck("Required configuration", "fail", text).to_dict()]
    r.errors.append(text); r.interpretation = "This analysis was not run because its prerequisites are not satisfied."; return r


def _table(r, name, frame):
    frame = frame.reset_index().rename(columns={"index": "variable"})
    r.tables.append({"name": name, "description": "Statistical output.", "columns": list(frame.columns), "rows": _to_jsonable(frame.to_dict("records"))})


class FactorAnalysisEngine(BaseAnalysis):
    name, category = "Factor Analysis", "Dimension Reduction"
    _purpose, _formula = "Factor analysis identifies latent variables that explain shared covariance.", r"X = \Lambda F + \epsilon"
    def run_analysis(self, df, config, type_map=None):
        cols = config.get("variables", []); r = _result(self, config, cols)
        if len(cols) < 3: return _fail(r, "Factor analysis needs at least three numeric variables.")
        X = _matrix(df, cols).dropna()
        if len(X) < max(20, len(cols) * 5): return _fail(r, "Factor analysis needs at least 20 complete observations and five per variable.")
        n = min(int(config.get("n_factors", min(3, len(cols)-1))), len(cols)-1)
        kmo, bart = kmo_test(X), bartlett_sphericity(X)
        checks = [AssumptionResult("KMO sampling adequacy", "pass" if kmo.get("adequate") else "warning", f"KMO = {kmo.get('kmo_total')}; {kmo.get('rating', '')}."), AssumptionResult("Bartlett sphericity", "pass" if bart.get("significant") else "warning", f"p = {bart.get('p')}; correlations should differ from identity.")]
        r.assumptions=[a.to_dict() for a in checks]; r.assumption_summary=summarize_assumptions(checks)
        Xs=StandardScaler().fit_transform(X); model=FactorAnalysis(n_components=n, random_state=42).fit(Xs); load=pd.DataFrame(model.components_.T,index=cols,columns=[f"Factor {i+1}" for i in range(n)])
        r.preprocessing=["Complete cases retained.","Variables standardised before extraction."]; r.results={"kmo":kmo,"bartlett":bart,"uniqueness":dict(zip(cols, model.noise_variance_)),"n_factors":n}; _table(r,"Factor Loadings",load); r.interpretation=f"{n} latent factor(s) were extracted from {len(cols)} variables. Inspect high absolute loadings to label factors."; r.limitations=["Factor count and rotation influence interpretation.","KMO and Bartlett diagnostics should guide use."]; self._add_code(r,"from sklearn.decomposition import FactorAnalysis\nX = StandardScaler().fit_transform(data[VARIABLES].dropna())\nloadings = FactorAnalysis(n_components=N).fit(X).components_.T"); return r


class MANOVAAnalysis(BaseAnalysis):
    name, category = "MANOVA", "Multivariate Hypothesis Testing"
    _purpose, _formula = "MANOVA tests whether group mean vectors differ across multiple outcomes.", r"\Lambda = |E| / |E + H|"
    def run_analysis(self, df, config, type_map=None):
        ys, group = config.get("dependent_variables", []), config.get("grouping_variable")
        r=_result(self,config,ys)
        if len(ys)<2 or not group: return _fail(r,"MANOVA needs two or more dependent variables and one grouping variable.")
        d=pd.concat([_matrix(df,ys),df[group]],axis=1).dropna(); groups=d[group].unique()
        if len(groups)<2 or len(d)<len(ys)*len(groups)*3: return _fail(r,"MANOVA needs at least two adequately sized groups.")
        Y=d[ys].values; grand=Y.mean(0); E=np.zeros((len(ys),len(ys))); H=E.copy()
        for g in groups:
            z=d.loc[d[group]==g,ys].values; E+=(z-z.mean(0)).T@(z-z.mean(0)); H+=len(z)*np.outer(z.mean(0)-grand,z.mean(0)-grand)
        wilks=float(np.linalg.det(E)/np.linalg.det(E+H)) if abs(np.linalg.det(E+H))>1e-12 else None
        r.results={"wilks_lambda":wilks,"groups":len(groups),"group_sizes":{str(g):int((d[group]==g).sum()) for g in groups}}; _table(r,"Group Means",d.groupby(group)[ys].mean())
        a=AssumptionResult("Multiple outcomes and groups","pass",f"{len(ys)} outcomes across {len(groups)} groups."); r.assumptions=[a.to_dict()];r.assumption_summary=summarize_assumptions([a]);r.preprocessing=["Rows missing selected values removed listwise."];r.interpretation=f"Wilks' Lambda is {wilks:.4f}. Smaller values indicate stronger separation of group mean vectors; assess alongside design and follow-up tests.";r.limitations=["This compact implementation reports Wilks' Lambda; use follow-up univariate tests cautiously.","Independence and covariance homogeneity remain design assumptions."];return r


class CanonicalCorrelation(BaseAnalysis):
    name, category="Canonical Correlation", "Relationships"
    _purpose,_formula="Canonical correlation finds maximally correlated linear combinations of two variable sets.",r"U=a'X,\;V=b'Y"
    def run_analysis(self,df,config,type_map=None):
        a,b=config.get("set_a",[]),config.get("set_b",[]);r=_result(self,config,a+b)
        if not a or not b:return _fail(r,"Canonical correlation needs two non-empty numeric variable sets.")
        d=pd.concat([_matrix(df,a),_matrix(df,b)],axis=1).dropna()
        if len(d)<20:return _fail(r,"Canonical correlation needs at least 20 complete observations.")
        n=min(len(a),len(b)); m=CCA(n_components=n).fit(StandardScaler().fit_transform(d[a]),StandardScaler().fit_transform(d[b]));u,v=m.transform(StandardScaler().fit_transform(d[a]),StandardScaler().fit_transform(d[b])); corrs=[float(np.corrcoef(u[:,i],v[:,i])[0,1]) for i in range(n)]
        r.results={"canonical_correlations":corrs};_table(r,"Canonical Correlations",pd.DataFrame({"function":range(1,n+1),"correlation":corrs}));r.interpretation=f"The first canonical correlation is {corrs[0]:.3f}; it summarizes the strongest linear association between the selected sets.";r.assumptions=[AssumptionResult("Complete numeric data","pass",f"{len(d)} observations used.").to_dict()];return r


class DiscriminantAnalysis(BaseAnalysis):
    name,category="Discriminant Analysis","Classification"
    _purpose,_formula="Discriminant analysis classifies observations into known groups using predictor measurements.",r"\delta_k(x)=x'\Sigma^{-1}\mu_k-\frac12\mu_k'\Sigma^{-1}\mu_k+\log\pi_k"
    def run_analysis(self,df,config,type_map=None):
        y,cols=config.get("class_variable"),config.get("predictors",[]);r=_result(self,config,cols)
        if not y or not cols:return _fail(r,"Discriminant analysis needs a class variable and numeric predictors.")
        d=pd.concat([_matrix(df,cols),df[y]],axis=1).dropna(); counts=d[y].value_counts()
        if len(counts)<2 or counts.min()<3:return _fail(r,"At least two classes with three observations each are required.")
        model=(QuadraticDiscriminantAnalysis() if config.get("model","lda").lower()=="qda" else LinearDiscriminantAnalysis()); X=d[cols].values; pred=cross_val_predict(model,X,d[y],cv=min(5,int(counts.min())));cm=confusion_matrix(d[y],pred,labels=counts.index)
        r.results={"accuracy":float(accuracy_score(d[y],pred)),"classes":counts.index.astype(str).tolist()};_table(r,"Confusion Matrix",pd.DataFrame(cm,index=counts.index,columns=counts.index));r.interpretation=f"Cross-validated classification accuracy was {r.results['accuracy']:.1%}.";r.assumptions=[AssumptionResult("Class sizes","pass",f"Smallest class has {counts.min()} observations.").to_dict()];return r


class CorrespondenceAnalysis(BaseAnalysis):
    name,category="Correspondence Analysis","Categorical Data"
    _purpose,_formula="Correspondence analysis maps association patterns in a categorical contingency table.",r"N=[n_{ij}]"
    def run_analysis(self,df,config,type_map=None):
        row,col=config.get("row_variable"),config.get("column_variable");r=_result(self,config,[x for x in [row,col] if x])
        if not row or not col:return _fail(r,"Correspondence analysis needs a row and a column categorical variable.")
        if row == col:return _fail(r,"Choose two different categorical variables for correspondence analysis.")
        tab=pd.crosstab(df[row],df[col]);
        if min(tab.shape)<2:return _fail(r,"Both categorical variables need at least two observed categories.")
        P=tab.values/tab.values.sum(); rr=P.sum(1);cc=P.sum(0);S=(P-np.outer(rr,cc))/np.sqrt(np.outer(rr,cc));U,s,Vt=np.linalg.svd(S,full_matrices=False); coords=U[:,:2]*s[:2]
        r.results={"inertia":float((s*s).sum()),"singular_values":s.tolist()};_table(r,"Contingency Table",tab);_table(r,"Row Coordinates",pd.DataFrame(coords,index=tab.index,columns=["Dimension 1","Dimension 2"]));r.interpretation="The coordinates summarize departures from independence; categories close together have similar association profiles.";return r


class IndependentComponentAnalysis(BaseAnalysis):
    name,category="Independent Component Analysis","Dimension Reduction"
    _purpose,_formula="ICA separates a numeric signal matrix into statistically independent components.",r"X=AS"
    def run_analysis(self,df,config,type_map=None):
        cols=config.get("variables",[]);r=_result(self,config,cols)
        if len(cols)<2:return _fail(r,"ICA needs at least two numeric variables.")
        X=_matrix(df,cols).dropna();n=min(int(config.get("n_components",2)),len(cols))
        if len(X)<10:return _fail(r,"ICA needs at least 10 complete observations.")
        m=FastICA(n_components=n,random_state=42,max_iter=1000);S=m.fit_transform(StandardScaler().fit_transform(X));r.results={"mixing_matrix":_to_jsonable(m.mixing_),"kurtosis":_to_jsonable(stats.kurtosis(S,axis=0))};_table(r,"Independent Components",pd.DataFrame(S,columns=[f"IC{i+1}" for i in range(n)]));r.interpretation=f"ICA extracted {n} independent component(s). Kurtosis and component distributions help assess non-Gaussian signals.";return r


class PartialLeastSquares(BaseAnalysis):
    name,category="Partial Least Squares","Prediction"
    _purpose,_formula="PLS predicts one or more outcomes while extracting components aligned with predictors and outcomes.",r"T=XW"
    def run_analysis(self,df,config,type_map=None):
        xs,ys=config.get("x_variables",[]),config.get("y_variables",[]);r=_result(self,config,xs+ys)
        if not xs or not ys:return _fail(r,"PLS needs predictor (X) and outcome (Y) variables.")
        d=pd.concat([_matrix(df,xs),_matrix(df,ys)],axis=1).dropna();n=min(int(config.get("n_components",2)),len(xs),len(d)-1)
        if len(d)<20:return _fail(r,"PLS needs at least 20 complete observations.")
        m=PLSRegression(n_components=n).fit(StandardScaler().fit_transform(d[xs]),d[ys]);pred=m.predict(StandardScaler().fit_transform(d[xs]));rmse=float(np.sqrt(np.mean((pred-d[ys].values)**2)));r.results={"rmse":rmse,"coefficients":_to_jsonable(m.coef_),"n_components":n};r.interpretation=f"PLS used {n} component(s) with in-sample RMSE {rmse:.4f}; use external or cross-validation for predictive claims.";return r


class MultidimensionalScaling(BaseAnalysis):
    name,category="Multidimensional Scaling","Similarity / Distance"
    _purpose,_formula="MDS places observations in a low-dimensional space that preserves pairwise dissimilarities.",r"D_{ij}=d(x_i,x_j)"
    def run_analysis(self,df,config,type_map=None):
        cols=config.get("variables",[]);r=_result(self,config,cols)
        if len(cols)<2:return _fail(r,"MDS needs at least two numeric variables.")
        X=_matrix(df,cols).dropna()
        if len(X)<4:return _fail(r,"MDS needs at least four complete observations.")
        m=MDS(n_components=2,metric=True,dissimilarity="euclidean",random_state=42,n_init=4,max_iter=300);z=m.fit_transform(StandardScaler().fit_transform(X));r.results={"stress":float(m.stress_),"coordinates":_to_jsonable(z)};_table(r,"MDS Coordinates",pd.DataFrame(z,columns=["Dimension 1","Dimension 2"]));r.interpretation=f"The two-dimensional MDS representation has stress {m.stress_:.3f}; lower stress indicates better distance preservation.";return r


