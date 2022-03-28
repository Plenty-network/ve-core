interface PlyStorageParams {
  admin: string;
}

export const getPlyStorage = (params: PlyStorageParams): string => {
  return `(Pair (Pair "${params.admin}" (Pair {} {Elt "" 0x697066733a2f2f64756d6d79})) (Pair {} (Pair {Elt 0 (Pair 0 {Elt "decimals" 0x3138; Elt "icon" 0x697066733a2f2f64756d6d79; Elt "name" 0x506c656e747920504c59; Elt "symbol" 0x504c59})} 0)))`;
};

interface VEStorageParams {
  baseToken: string;
}

export const getVEStorage = (params: VEStorageParams): string => {
  return `(Pair (Pair (Pair {} (Pair "${params.baseToken}" 0)) (Pair {} (Pair {} 0))) (Pair (Pair {} (Pair {} {})) (Pair {} (Pair {} 0))))`;
};

interface VoterStorageParams {
  plyAddress: string;
  veAddress: string;
}

export const getVoterStorage = (params: VoterStorageParams): string => {
  return `(Pair (Pair (Pair {} (Pair "KT1TezoooozzSmartPyzzDYNAMiCzzpLu4LU" (Pair 2000000000000000000000000 (Pair 0 0)))) (Pair 0 (Pair {} "KT1TezoooozzSmartPyzzDYNAMiCzzpLu4LU"))) (Pair (Pair "${params.plyAddress}" (Pair {} {})) (Pair {} (Pair {} "${params.veAddress}"))))`;
};

interface FactoryStorageParams {
  admin: string;
  plyAddress: string;
  veAddress: string;
  voterAddress: string;
}

export const getFactoryStorage = (params: FactoryStorageParams): string => {
  return `(Pair (Pair "${params.admin}" (Pair {} "tz1RBkXZSiQb3fS7Sg3zbFdPMBFPJUNHdcFo")) (Pair "${params.plyAddress}" (Pair "${params.veAddress}" "${params.voterAddress}")))`;
};

interface FeeDistributorStorageParams {
  factoryAddress: string;
  voterAddress: string;
}

export const getFeeDistributorStorage = (params: FeeDistributorStorageParams): string => {
  return `(Pair (Pair {} {}) (Pair {} (Pair "${params.factoryAddress}" "${params.voterAddress}")))`;
};
